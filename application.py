import os
import sys
import json
import jwt
import re
import jwt
import base64
import tempfile
from datetime import datetime

from flask import Flask, request, session, flash, url_for, redirect, \
     render_template, abort, send_from_directory, Response
from application.models import User, Job, Vendor, Shipment, ShipmentPhoto
from application import db
from application import apUtils
from flask.ext.mail import Mail
from flask.ext.mail import Message
from threading import Thread

application = Flask(__name__)
# ONLY turn this on when testing.   Otherwise, it cause problems with DB Session timeouts.
# application.debug=True
application.secret_key = '3915408C-CFCC-47D4-86B4-E2A2819804B6'

application.config['MAIL_SERVER'] = 'smtp.yandex.com'
application.config['MAIL_PORT'] = 465
application.config['MAIL_USE_SSL'] = True 
application.config['MAIL_USERNAME'] = 'aeroengineer@yandex.com'
application.config['MAIL_PASSWORD'] = 'yd082893!'

mail = Mail(application)

AllJobs = []
WarningMessage = ""
MobileTTL = 60 * 60
ERR_NONE = 100
ERR_NO_USER = 101
ERR_CALL_FAILED = 102

IMAGE_DIR = "/static/images/"

def user_for_id(userId) :
    user = None

    try :
    	user = db.session.query(User).filter_by(id=userId).first()
    except Exception as ex :
    	print 'Exception fetching user id [' + str(vendorId) + '] ' + str(ex)
    	user = None

    return user

def job_for_id(jobId) :
    job = None

    try :
    	job = db.session.query(Job).filter_by(id=jobId).first()
    except Exception as ex :
    	job = None
    	print 'Exception fetching job for id [' + str(jobId) + '] = ' + str(ex)

    return job

def vendor_for_id(vendorId) :
    vendor = None

    try :
    	vendor = db.session.query(Vendor).filter_by(id=vendorId).first()
    except Exception as ex :
    	print 'Exception fetching vendor id [' + str(vendorId) + '] ' + str(ex)
    	vendor = None

    return vendor

def shipment_for_id(shipmentId) :
    shipment = None

    try :
    	shipment = db.session.query(Shipment).filter_by(id=shipmentId).first()
    except Exception as ex :
    	print 'Exception fetching shipment id [' + str(shipmentId) + '] ' + str(ex)
    	shipment = None

    return shipment

def shipment_photo_for_id(shipmentPhotoId) :
    shipmentPhoto = None

    try :
    	shipmentPhoto = db.session.query(ShipmentPhoto).filter_by(id=shipmentPhotoId).first()
    except Exception as ex :
    	print 'Exception fetching shipment Photo id [' + str(shipmentPhotoId) + '] ' + str(ex)
    	shipmentPhoto = None

    return shipmentPhoto

def uri_for_shipment_photo_id(shipmentPhotoId) :
    imageFilename = os.path.dirname(os.path.realpath(__file__)) + IMAGE_DIR + "shipmentPhoto." + str(shipmentPhotoId) + ".jpg"
    return imageFilename

def jwt_for_user(user) :
    payload = {}
    payload['userId'] = str(user.id)
    now = int(datetime.now().strftime("%s"))
    expiration_time = now +  MobileTTL
    payload['expiration_time'] = str(expiration_time)
    encoded = jwt.encode(payload, application.secret_key, algorithm='HS256')

    return encoded

def user_for_jwt(encoded) :
    payload = jwt.decode(encoded, application.secret_key, algorithm=['HS256'])
    userId = payload['userId']
    expiration_time = payload['expiration_time']
    now = int(datetime.now().strftime("%s"))

    if now > int(expiration_time) :
    	raise Exception("User Session has expired")

    user = user_for_id(userId)

    if None == user :
    	raise Exception("User not found.")

    return user

def date_from_mobile(prefix, dict) :
    returnDate = None
    name = prefix + "Date"
    dateString = dict[name]

    try :
    	returnDate = datetime.strptime(dateString, '%Y-%m-%d %H:%M:%S')
    except Exception as ex:
    	returnDate = None

    print 'PJC date for ' + str(dateString) + ' is ' + str(returnDate)
    return returnDate

def date_with_prefix(prefix, form) :
    returnDate = None
    month = form[prefix + 'month']
    day = form[prefix + 'day']
    year = form[prefix + 'year']
    hour = form[prefix + 'hour']
    minute = form[prefix + 'minute']
    meridian = form[prefix + 'meridian']

    dateString = str(month) + '/' + str(day) + '/' + str(year) + ' ' + str(hour) + ':' + str(minute) + ':' + str(meridian)

    try :
    	returnDate = datetime.strptime(dateString, '%m/%d/%Y %I:%M:%p')
    except Exception as ex:
    	returnDate = None

    return returnDate

def save_shipment(shipment, request):
    description = request.form['description']
    shippedDate = date_with_prefix('shipped_', request.form)
    expectedDate = date_with_prefix('expected_', request.form)
    arrivalDate = date_with_prefix('arrival_', request.form)

    shipment.description = description
    shipment.shippedDate = shippedDate
    shipment.expectedDate = expectedDate
    shipment.arrivalDate = arrivalDate

    try :
        db.session.commit()
    except Exception as ex:
        db.session.rollback()
        print 'Unable to save Shipment [%s]' % str(ex)
    try :
        db.session.commit()
    except Exception as ex:
        db.session.rollback()
        print 'Unable to save Shipment [%s]' % str(ex)

    return render_job_page()

def save_vendor(vendor, request):
    name = request.form['name']

    vendor.name = name

    try :
        db.session.commit()
    except Exception as ex:
        db.session.rollback()
        print 'Unable to save vendor [%s]' % str(ex)

    return render_job_page()

def render_job_page():
    job = job_for_id(session['jobId'])
    shipments = job.shipments
    shipments.sort()

    return render_template('listVendors.html', Job=job, Shipments=shipments)

@application.before_first_request
def startup() :
    # Fetch Jobs
    global AllJobs

    try :
    	AllJobs = db.session.query(Job).all()
    except Exception as ex :
    	AllJobs = []
    	print 'Exception fetching Jobs ' + str(ex)

@application.before_request
def before_request() :
    global WarningMessage
    # Clear warnings
    WarningMessage = ""

    # Ensure that we are logged in.
    userDict = session.get('user')

    print 'PJC processing : ' + str(request.endpoint)
    print 'PJC userDict : ' + str(userDict)
    if None == userDict :
    	if request.endpoint and request.endpoint.startswith('mobile_') :
    		pass
    	elif request.endpoint == 'login_user' :
    		pass
    	elif request.endpoint == 'new_user' :
    		pass
    	elif request.endpoint == 'create_user' :
    		pass
    	else :
    		return render_template('loginUser.html', warning=WarningMessage)
    elif userDict['passwordRequiresReset'].lower() in ("yes", "true", "t", "1") :
    	if request.endpoint == 'reset_password' :
    		pass
    	else :
    		return render_template('resetPassword.html', user=userDict, warning=WarningMessage)

@application.route('/')
def index():
    global AllJobs
    return render_template('listJobs.html', Jobs=AllJobs)

@application.route('/loginUser',methods=['POST'])
def login_user():
    global AllJobs
    global WarningMessage
    email = request.form['email']
    password = request.form['password']
    user = None

    try :
    	user = db.session.query(User).filter_by(email=email.lower()).first()
    except Exception as ex :
    	print 'Exception fetching User id [' + str(email) + '] ' + str(ex)
    	user = None

    if None == user :
    	WarningMessage = "No user for email " + str(email)
    	return render_template('loginUser.html', warning=WarningMessage)
    else :
    	if user.passwordsMatch(password) :
    		session['user'] = user.asDict()
    		if user.asDict()['passwordRequiresReset'].lower() in ("yes", "true", "t", "1") :
    			return render_template('resetPassword.html', user=user.asDict(), warning=WarningMessage)
    		else :
    			return render_template('listJobs.html', Jobs=AllJobs)
    	else :
    		WarningMessage = "Your password is incorrect."
    		return render_template('loginUser.html', warning=WarningMessage)

@application.route('/logout',methods=['POST','GET'])
def logout_user():
    global AllJobs
    global WarningMessage

    session['user'] = None
    WarningMessage = "User has been logged out."

    return render_template('loginUser.html', warning=WarningMessage)

@application.route('/selectJob',methods=['POST'])
def select_job():
    jobId = request.form['jobId']
    job = job_for_id(jobId)

    session['jobId'] = job.id
    return render_job_page()

def send_email(recipients,subject,text) :
    msg = Message(subject, sender='aeroengineer@yandex.com', recipients=recipients)
    msg.body = text
    thr = Thread(target=send_async_email, args=[application, msg]) 
    thr.start()

def send_async_email(app, msg):
    try :
    	with app.app_context(): 
    		resp = mail.send(msg)
    		print 'PJC mail response is ' + str(resp)
    except Exception as ex :
    	print 'Email exception of ' + str(ex)

@application.route('/newUser',methods=['POST','GET'])
def new_user():
    return render_template('newUser.html')

@application.route('/createUser',methods=['POST'])
def create_user():
    global WarningMessage
    user = User()
    user.setEmail(request.form['email'])
    user.firstName = request.form['firstName']
    user.lastName = request.form['lastName']
    tmpPassword = User.tmpPassword()
    user.setPassword(tmpPassword)
    user.passwordRequiresReset = True

    db.session.add(user)
    try :
        db.session.commit()
    	send_email([user.email],'Welcome to CrownCorr','Your temporary password is ' + tmpPassword)
    	print 'PJC: Welcome to CrownCorr, Your temporary password is ' + tmpPassword
    	WarningMessage = "User " + str(user.email) + " has been created.   Check your email inbox for a temporary password"
    except Exception as ex:
        db.session.rollback()
    	WarningMessage = "Unable to create new User " + str(user.email) 
        print 'Unable to save User [%s]' % str(ex)

    return render_template('loginUser.html', warning=WarningMessage)

@application.route('/resetPassword',methods=['POST'])
def reset_password():
    global WarningMessage
    userId = request.form['userId']

    user = user_for_id(userId)
    if user :
    	oldPassword = request.form['oldPassword']
    	if user.passwordsMatch(oldPassword) :
    		password = request.form['password']
    		user.setPassword(password)
    		user.passwordRequiresReset = False
    		try :
    			db.session.commit()
    			session['user'] = user.asDict()
    			WarningMessage = "Password successfully reset"
    			return render_template('listJobs.html', Jobs=AllJobs)
    		except Exception as ex:
    			db.session.rollback()
    			print 'Unable to update User [%s]' % str(ex)
    			WarningMessage = "Error updating User"
    			return render_template('resetPassword.html', user=user.asDict(), warning=WarningMessage)
    	else :
    		WarningMessage = "Old Password does not match"
    		return render_template('resetPassword.html', user=user.asDict(), warning=WarningMessage)
    else :
    	WarningMessage = "Failed to update user"
    	session['user'] = None
    	return render_template('loginUser.html', warning=WarningMessage)

@application.route('/cancel',methods=['POST','GET'])
def cancel() :
    return render_job_page()

@application.route('/newShipment',methods=['POST'])
def new_shipment():
    jobId = request.form['jobId']
    vendorId = request.form['vendorId']
    shipment = Shipment()
    shipment.jobId = jobId
    shipment.vendorId = vendorId
    vendor = vendor_for_id(vendorId)
    job = job_for_id(jobId)

    return render_template('newShipment.html', Shipment=shipment, Vendor=vendor, Job=job)

@application.route('/editShipment',methods=['POST'])
def edit_shipment():
    shipmentId = request.form['shipmentId']
    shipment = shipment_for_id(shipmentId)

    return render_template('editShipment.html', Shipment=shipment, Photos=shipment.photos)

@application.route('/createShipment',methods=['POST'])
def create_shipment():
    shipment = Shipment()
    jobId = request.form['jobId']
    vendorId = request.form['vendorId']
    shipment.jobId = jobId
    shipment.vendorId = vendorId
    db.session.add(shipment)

    return save_shipment(shipment, request)

@application.route('/cancelEditShipment',methods=['POST'])
def cancel_edit_shipment() :
    return render_job_page()

@application.route('/updateShipment',methods=['POST'])
def update_shipment():
    shipmentId = request.form['shipmentId']
    shipment = shipment_for_id(shipmentId)

    return save_shipment(shipment, request)

@application.route('/newVendor',methods=['POST'])
def new_vendor():
    jobId = request.form['jobId']
    vendor = Vendor()
    vendor.jobId = jobId

    return render_template('newVendor.html', Vendor=vendor)

@application.route('/editVendor',methods=['POST'])
def edit_vendor():
    vendorId = request.form['vendorId']
    vendor = vendor_for_id(vendorId)

    return render_template('editVendor.html', Vendor=vendor)

@application.route('/createVendor',methods=['POST'])
def create_vendor():
    vendor = Vendor()
    jobId = request.form['jobId']
    vendor.jobId = jobId
    db.session.add(vendor)

    return save_vendor(vendor, request)

@application.route('/updateVendor',methods=['POST'])
def update_vendor():
    vendorId = request.form['vendorId']
    vendor = None

    try :
    	vendor = db.session.query(Vendor).filter_by(id=vendorId).first()
    except Exception as ex :
    	print 'Exception fetching vendor id [' + str(vendorId) + '] ' + str(ex)
    	vendor = None

    return save_vendor(vendor, request)

@application.route('/mLoginUser',methods=['POST'])
def mobile_login_user():
    dict = json.loads(str(request.data))
    user = None
    email = dict['email']
    password = dict['password']
    error = None
    status = ERR_NO_USER
    retVal = {}

    try :
    	user = db.session.query(User).filter_by(email=email.lower()).first()
    except Exception as ex :
    	print 'Exception fetching User id [' + str(email) + '] ' + str(ex)
    	user = None

    if None == user :
    	error = "No user for email " + str(email)
    else :
    	if user.passwordsMatch(password) :
    		retVal['access_token'] = jwt_for_user(user)
    		retVal['user'] = str(user.asDict())
    		status = ERR_NONE
    	else :
    		error = "Your password is incorrect."

    retVal['status'] = status
    retVal['error'] = error

    return Response(json.dumps(retVal),  mimetype='application/json')

@application.route('/mListJobs',methods=['POST'])
def mobile_list_jobs():
    dict = json.loads(str(request.data))
    access_token = None
    user = None
    global AllJobs
    status = ERR_NO_USER
    error = None
    retVal = {}

    try :
    	access_token = dict['access_token']
    	user = user_for_jwt(access_token)
    	if user :
    		# Update the access_token
    		retVal['access_token'] = jwt_for_user(user)
    		jobs = []
    		for job in AllJobs :
    			jobs.append(job.asDict())
    		retVal['jobs'] = jobs
    		status = ERR_NONE
    	else :
    		status = ERR_NO_USER
    		error = "No user defined"
    except Exception as ex :
    	error = str(ex)
    	status = ERR_NO_USER

    retVal['status'] = status
    retVal['error'] = error

    return Response(json.dumps(retVal),  mimetype='application/json')

@application.route('/mSelectJob',methods=['POST'])
def mobile_select_job() :
    dict = json.loads(str(request.data))
    access_token = None
    user = None
    error = None
    status = ERR_CALL_FAILED
    retVal = {}

    try :
    	access_token = dict['access_token']
    	user = user_for_jwt(access_token)
    	jobId = dict['jobId']
    	if user :
    		# Update the access_token
    		retVal['access_token'] = jwt_for_user(user)
    		job = job_for_id(jobId)
    		retVal['job'] = str(job.asDict())
    		shipments = []
    		for shipment in job.shipments :
    			shipments.append(shipment.asDict())
    		retVal['shipments'] = str(shipments)
    		status = ERR_NONE
    	else :
    		status = ERR_NO_USER
    		error = "No user defined"
    except Exception as ex :
    	error = str(ex)
    	status = ERR_NO_USER

    retVal['status'] = status
    retVal['error'] = error

    return Response(json.dumps(retVal),  mimetype='application/json')

@application.route('/mEditShipment',methods=['POST'])
def mobile_edit_shipment() :
    dict = json.loads(str(request.data))
    access_token = None
    user = None
    error = None
    status = ERR_CALL_FAILED
    retVal = {}

    try :
    	access_token = dict['access_token']
    	user = user_for_jwt(access_token)
    	if user :
    		# Update the access_token
    		retVal['access_token'] = jwt_for_user(user)
    		shipmentId = dict['shipmentId']
    		shipment = shipment_for_id(shipmentId)
    		if shipment :
    			shipment.shippedDate = date_from_mobile('shipped', dict)
    			shipment.expectedDate = date_from_mobile('expected', dict)
    			shipment.arrivalDate = date_from_mobile('arrival', dict)
    			shipment.description = dict['description']
    			try :
    				db.session.commit()
    				status = ERR_NONE
    			except Exception as ex :
    				db.session().rollback()
    				error = str(ex)
    		else :
    			error = "Shipment not found"
    	else :
    		status = ERR_NO_USER
    		error = "No user defined"
    except Exception as ex :
    	error = str(ex)
    	status = ERR_NO_USER

    retVal['status'] = status
    retVal['error'] = error

    return Response(json.dumps(retVal),  mimetype='application/json')

@application.route('/mPostPhoto',methods=['POST'])
def mobile_post_photo() :
    dict = json.loads(str(request.data))
    access_token = None
    user = None
    error = None
    status = ERR_CALL_FAILED
    retVal = {}

    try :
    	access_token = dict['access_token']
    	user = user_for_jwt(access_token)
    	if user :
    		# Update the access_token
    		retVal['access_token'] = jwt_for_user(user)
    		shipmentId = dict['shipmentId']
    		shipment = shipment_for_id(shipmentId)
    		if shipment :
                        image_64_encode = str(dict['image'])
                        if image_64_encode == None :
                                error = "No photo was submitted."
                        else :
                                image_64_decode = base64.decodestring(image_64_encode)
                                shipmentPhoto = ShipmentPhoto()
                                shipmentPhoto.shipment = shipment
                                shipmentPhoto.image = image_64_decode
                                shipmentPhoto.photoDate = datetime.now()
                                try :
                                	db.session.add(shipmentPhoto)
                                	db.session.commit()
                                	retVal['id'] = shipmentPhoto.id
                                	imageFilename = uri_for_shipment_photo_id(shipmentPhoto.id)
                                	file = open(imageFilename, 'wb') # create a writable image and write the decoding result
                                	file.write(image_64_decode)
                                	file.close()
                                        status = ERR_NONE
                                except Exception as ex:
                                	db.session.rollback()
                                	print 'Unable to save ShipmentPhoto [%s]' % str(ex)

                                # tmpFilename = '/tmp/' + next(tempfile._get_candidate_names())
                                # try :
                                        # image_64_decode = base64.decodestring(image_64_encode)
                               		# file = open(imageFilename, 'wb') # create a writable image and write the decoding result
                               		# file.write(image_64_decode)
                               		# file.close()
                                        # os.remove(tmpFilename)
                                        # status = ERR_NONE
                                # except Exception as ex :
                                        # print "Post Photo exception " + str(ex)
                                        # error = "Unable to decode photo data."
    	else :
    		status = ERR_NO_USER
    		error = "No user defined"
    except Exception as ex :
    	error = str(ex)
    	status = ERR_NO_USER

    retVal['status'] = status
    retVal['error'] = error

    return Response(json.dumps(retVal),  mimetype='application/json')

@application.route('/mFetchPhotosForShipment',methods=['POST'])
def mobile_fetch_photos_for_shipment():
    dict = json.loads(str(request.data))
    access_token = None
    user = None
    error = None
    status = ERR_CALL_FAILED
    retVal = {}

    try :
    	access_token = dict['access_token']
    	user = user_for_jwt(access_token)
    	if user :
    		# Update the access_token
    		retVal['access_token'] = jwt_for_user(user)
    		shipmentId = dict['shipmentId']
    		shipment = shipment_for_id(shipmentId)
    		if shipment :
    			retVal['shipment'] = shipment.asDict()
    			photos = []
    			for photo in shipment.photos :
    				photoDict = photo.asDict()
    				imageFilename = uri_for_shipment_photo_id(photo.id)
    				with open(imageFilename, "rb") as image_file:
    					encoded_string = base64.b64encode(image_file.read())
    					photoDict['image'] = encoded_string
    				photos.append(photoDict)
    			retVal['photos'] = photos
    			status = ERR_NONE
    	else :
    		status = ERR_NO_USER
    		error = "No user defined"
    except Exception as ex :
    	error = str(ex)
    	status = ERR_NO_USER

    retVal['status'] = status
    retVal['error'] = error

    return Response(json.dumps(retVal),  mimetype='application/json')

@application.route('/mDeleteShipmentPhoto',methods=['POST'])
def mobile_delete_shipment_photo():
    dict = json.loads(str(request.data))
    access_token = None
    user = None
    error = None
    status = ERR_CALL_FAILED
    retVal = {}

    try :
    	access_token = dict['access_token']
    	user = user_for_jwt(access_token)
    	if user :
    		# Update the access_token
    		retVal['access_token'] = jwt_for_user(user)
    		shipmentPhotoId = dict['shipmentPhotoId']
    		shipmentPhoto = shipment_photo_for_id(shipmentPhotoId)
    		if shipmentPhoto :
    			try :
    				db.session.delete(shipmentPhoto)
    				db.session.commit()
    				status = ERR_NONE
    			except Exception as ex:
    				db.session.rollback()
    				print 'Unable to delete ShipmentPhoto [%s]' % str(ex)
    		else :
    			error = "No ShipmentPhoto for Id " + str(shipmentPhotoId)
    	else :
    		status = ERR_NO_USER
    		error = "No user defined"
    except Exception as ex :
    	error = str(ex)
    	status = ERR_NO_USER

    retVal['status'] = status
    retVal['error'] = error

    return Response(json.dumps(retVal),  mimetype='application/json')

if __name__ == "__main__":
	# application.run(debug=True,host='0.0.0.0',port=8888)
	application.run(debug=True,host='172.20.10.4',port=9999)

