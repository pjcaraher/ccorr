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
from application.models import User, Job, Shipment, ShipmentPhoto, Vendor
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
AllVendors = []
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
    	# Sometimes the new Object did not make it in to the Session.
    	if None == user :
                db.session.expire_all()
                db.session.commit()
                user = db.session.query(User).filter_by(id=userId).first()
    except Exception as ex :
        db.session.rollback()
    	print 'Exception fetching user id [' + str(userId) + '] ' + str(ex)
    	user = None

    return user

def user_for_email(email) :
    user = None

    try :
    	user = db.session.query(User).filter(User.email.ilike(email)).first()
    except Exception as ex :
        db.session.rollback()
    	print 'Exception fetching user for email [' + str(email) + '] ' + str(ex)
    	user = None

    return user

def job_for_id(jobId) :
    job = None

    try :
    	job = db.session.query(Job).filter_by(id=jobId).first()
    	# Sometimes the new Object did not make it in to the Session.
    	if None == job :
                db.session.expire_all()
                db.session.commit()
                job = db.session.query(Job).filter_by(id=jobId).first()
    except Exception as ex :
        db.session.rollback()
    	job = None
    	print 'Exception fetching job for id [' + str(jobId) + '] = ' + str(ex)

    return job

def vendor_for_id(vendorId) :
    vendor = None

    try :
    	vendor = db.session.query(Vendor).filter_by(id=vendorId).first()
    	# Sometimes the new Object did not make it in to the Session.
    	if None == vendor :
                db.session.expire_all()
                db.session.commit()
                vendor = db.session.query(Vendor).filter_by(id=vendorId).first()
    except Exception as ex :
        db.session.rollback()
    	vendor = None
    	print 'Exception fetching vendor for id [' + str(vendorId) + '] = ' + str(ex)

    return vendor

def shipment_for_id(shipmentId) :
    shipment = None

    try :
    	shipment = db.session.query(Shipment).filter_by(id=shipmentId).first()
    	# Sometimes the new Object did not make it in to the Session.
    	if None == shipment :
                db.session.expire_all()
                db.session.commit()
                shipment = db.session.query(Shipment).filter_by(id=shipmentId).first()
    except Exception as ex :
        db.session.rollback()
    	print 'Exception fetching shipment id [' + str(shipmentId) + '] ' + str(ex)
    	shipment = None

    return shipment

def shipment_photo_for_id(shipmentPhotoId) :
    shipmentPhoto = None

    try :
    	shipmentPhoto = db.session.query(ShipmentPhoto).filter_by(id=shipmentPhotoId).first()
    except Exception as ex :
        db.session.rollback()
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

def jobIds_from_form(form) :
    jobIds = []

    for key in form.keys() :
    	if key.startswith("jobId_") :
    		jobId = key[6:]
    		jobIds.append(jobId)

    return jobIds

def jobs_from_form(form) :
    jobIds = jobIds_from_form(form)
    jobs = []

    for jobId in jobIds:
    	job = job_for_id(jobId)
    	jobs.append(job)

    return jobs

def form_bool_for_key(form, key) :
    torf = False

    if key in form.keys() :
	if form[key].lower() == 'on' :
    		torf = True

    return torf

def vendorJobConfig_from_form(form) :
    config = VendorJobConfig()
    return update_JobConfig_from_form(config, form)

def update_jobConfig_from_form(job, form) :
    job.showDeliveryNumber = form_bool_for_key(form,'showDeliveryNumber')
    job.showContactName = form_bool_for_key(form,'showContactName')
    job.showContactNumber = form_bool_for_key(form,'showContactNumber')
    job.showBOLNumber = form_bool_for_key(form,'showBOLNumber')
    job.showSpecialInstructions = form_bool_for_key(form,'showSpecialInstructions')
    job.showDescriptionOfGoods = form_bool_for_key(form,'showDescriptionOfGoods')
    job.showTruckingCompany = form_bool_for_key(form,'showTruckingCompany')
    job.showNumberOfPackages = form_bool_for_key(form,'showNumberOfPackages')
    job.showTypeOfTruck = form_bool_for_key(form,'showTypeOfTruck')
    job.showTrackingNumber = form_bool_for_key(form,'showTrackingNumber')
    job.showWeightOfLoad = form_bool_for_key(form,'showWeightOfLoad')
    job.showVendorNotes = form_bool_for_key(form,'showVendorNotes')
    job.showDeliveryDate = form_bool_for_key(form,'showDeliveryDate')
    job.showDateLoaded = form_bool_for_key(form,'showDateLoaded')
    job.attachBOL = form_bool_for_key(form,'attachBOL')
    job.attachPackingList = form_bool_for_key(form,'attachPackingList')
    job.attachPhotos = form_bool_for_key(form,'attachPhotos')
    job.attachMap = form_bool_for_key(form,'attachMap')
    
    return job

def stringForShipmentKey(key, form) :
    retVal = None
    value = form[key]

    if value and len(value) > 0 :
    	retVal = value

    return retVal

def intForShipmentKey(key, form) :
    retVal = None

    value = form[key]
    
    if isinstance(value, (int, long)) :
    	retVal = int(value)

    return retVal

def update_shipment_from_form(shipment, form) :
    if "description" in form.keys() :
    	shipment.description = stringForShipmentKey("description", form)
    if "deliveryNumber" in form.keys() :
    	shipment.deliveryNumber = stringForShipmentKey("deliveryNumber", form)
    if "numberOfPackages" in form.keys() :
    	shipment.numberOfPackages = intForShipmentKey('numberOfPackages', form)
    if "truckType" in form.keys() :
    	shipment.truckType = stringForShipmentKey("truckType", form)
    if "weight" in form.keys() :
    	shipment.weight = stringForShipmentKey("weight", form)
    if "truckingCompany" in form.keys() :
    	shipment.truckingCompany = stringForShipmentKey("truckingCompany", form)
    if "specialInstructions" in form.keys() :
    	shipment.specialInstructions = stringForShipmentKey("specialInstructions", form)
    if "trackingNumber" in form.keys() :
    	shipment.trackingNumber = stringForShipmentKey("trackingNumber", form)
    if "vendorNotes" in form.keys() :
    	shipment.vendorNotes = stringForShipmentKey("vendorNotes", form)

    return

def save_shipment(shipment, request):
    shippedDate = date_with_prefix('shipped_', request.form)
    expectedDate = date_with_prefix('expected_', request.form)
    arrivalDate = date_with_prefix('arrival_', request.form)

    shipment.shippedDate = shippedDate
    shipment.expectedDate = expectedDate
    shipment.arrivalDate = arrivalDate

    try :
        db.session.commit()
    except Exception as ex:
        db.session.rollback()
        print 'Unable to save Shipment [%s]' % str(ex)

    return render_job_page()

def render_jobs_page(user=None):
    global AllJobs
    jobs = []
    session['jobId'] = None
    userDict = session['user']
    user = None

    if userDict:
    	user = user_for_id(userDict['id'])

    if user :
    	jobs = user.jobs
	if user.hasPermission(2) :  # If we are Admin
		jobs = AllJobs
	elif user.hasPermission(3) :  # If we are a PM
		jobs = user.jobs
	elif user.hasPermission(4) :  # If we are a Vendor
		vendor = vendor_for_id(user.vendorId)
		if vendor :
			jobs = vendor.jobs

		if len(jobs) == 1 :
			session['jobId'] = jobs[0].id
			return render_job_page()
		else :
    			return render_template('listJobs.html', Jobs=jobs, User=user)

    return render_template('pmMainPage.html', Jobs=jobs, User=user)

def render_job_page():
    job = job_for_id(session['jobId'])
    shipments = job.shipments
    shipments.sort()
    openShipments = []
    completedShipments = []
    userDict = session['user']
    user = None

    if userDict:
    	user = user_for_id(userDict['id'])

    	if user.permissionId == 4 :  # If we are a Vendor show only our Deliveries
    		for shipment in reversed(shipments):
    			if shipment.vendorId != user.vendorId :
    				shipments.remove(shipment)

    for shipment in shipments :
    	if shipment.arrivalDate :
    		completedShipments.append(shipment)
    	else :
    		openShipments.append(shipment)

    return render_template('displayJob.html', Job=job, OpenShipments=openShipments, CompletedShipments=completedShipments, User=user)

@application.before_first_request
def startup() :
    # Fetch Jobs
    global AllJobs
    # Fetch Vendors
    global AllVendors

    try :
    	AllJobs = db.session.query(Job).all()
    except Exception as ex :
        db.session.rollback()
    	AllJobs = []
    	print 'Exception fetching Jobs ' + str(ex)

    try :
    	AllVendors = db.session.query(User).filter_by(permissionId=4)
    except Exception as ex :
        db.session.rollback()
    	AllVendors = []
    	print 'Exception fetching Vendors ' + str(ex)

@application.before_request
def before_request() :
    global WarningMessage
    # Clear warnings
    WarningMessage = ""

    # Ensure that we are logged in.
    userDict = session.get('user')

    print 'PJC processing : [' + str(request.endpoint) + ']'

    # Make certain that we have cleared out any prior user
    if request.endpoint == 'logout_user' :
    	userDict = None
    	session['user'] = None

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
    return render_template('pmMainPage.html', Jobs=AllJobs)

@application.route('/refreshDB')
def refresh_db():
    db.session.expire_all()

@application.route('/loginUser',methods=['POST'])
def login_user():
    global AllJobs
    global WarningMessage
    email = request.form['email']
    password = request.form['password']
    user = None

    try :
    	user = db.session.query(User).filter_by(email=email.lower()).first()
    	# Sometimes the new Object did not make it in to the Session.
    	if None == user :
                db.session.expire_all()
                db.session.commit()
                user = db.session.query(User).filter_by(email=email.lower()).first()
    except Exception as ex :
        db.session.rollback()
    	sys.stderr.write('Exception fetching User id [' + str(email) + '] ' + str(ex))
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
    			return render_jobs_page(user)
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

@application.route('/mainPage',methods=['GET'])
def main_page() :
    return render_jobs_page()

@application.route('/selectJob',methods=['POST'])
def select_job():
    jobId = request.form['jobId']
    job = job_for_id(jobId)

    session['jobId'] = job.id
    return render_job_page()

@application.route('/selectJob',methods=['GET'])
def select_job_get():
    jobId = request.args.get('jobId', 0, type=int)
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

@application.route('/newJob',methods=['GET'])
def new_job():
    global WarningMessage
    userDict = session['user']
    user = None

    if userDict:
    	user = user_for_id(userDict['id'])
    
    if user == None :
    	WarningMessage = "No logged in User"

    return render_template('newJob.html', User=user, warning=WarningMessage)

@application.route('/createJob',methods=['POST'])
def create_job():
    global WarningMessage
    global AllJobs
    job = Job()
    job.name = request.form['name']
    job.number = request.form['number']
    job.address = request.form['address']
    job.instructions = request.form['instructions']
    userDict = session['user']
    user = None
    templateName = "newJob.html"

    update_jobConfig_from_form(job, request.form)

    if userDict:
    	user = user_for_id(userDict['id'])

    db.session.add(job)
    try :
        db.session.commit()
    	AllJobs = db.session.query(Job).all()
    	WarningMessage = job.name + " was successfully created"
        templateName = "updateJob.html"
    except Exception as ex:
        db.session.rollback()
        templateName = "newJob.html"
    	WarningMessage = "Unable to create new Job " + str(ex.message)
        print 'Unable to create Job [%s]' % str(ex)

    return render_template(templateName, User=user, Job=job, warning=WarningMessage)

@application.route('/updateJob',methods=['POST'])
def update_job():
    global WarningMessage
    global AllJobs
    jobId = request.form['jobId']
    job = job_for_id(jobId)
    job.name = request.form['name']
    job.number = request.form['number']
    job.address = request.form['address']
    job.instructions = request.form['instructions']
    userDict = session['user']
    user = None

    update_jobConfig_from_form(job, request.form)

    if userDict:
    	user = user_for_id(userDict['id'])

    db.session.add(job)
    try :
        db.session.commit()
    	AllJobs = db.session.query(Job).all()
    	WarningMessage = job.name + " was successfully updated"
    except Exception as ex:
        db.session.rollback()
    	WarningMessage = "Unable to update Job " + str(ex.message)
        print 'Unable to create Job [%s]' % str(ex)

    return render_template("updateJob.html", User=user, Job=job, warning=WarningMessage)

@application.route('/newUser',methods=['POST','GET'])
def new_user():
    global WarningMessage
    global AllJobs
    userDict = session['user']
    currentPermission = int(userDict['permissionId'])
    
    return render_template('newUser.html', UserPermission=currentPermission, Jobs=AllJobs, warning=WarningMessage)

@application.route('/newVendor',methods=['GET'])
def new_vendor():
    global WarningMessage
    global AllJobs
    
    return render_template('newVendor.html', Jobs=AllJobs, warning=WarningMessage)

@application.route('/editVendor',methods=['GET'])
def edit_vendor():
    global WarningMessage
    global AllJobs
    vendorId = request.args.get('vendorId', 0, type=int)
    vendor = vendor_for_id(vendorId)
    
    return render_template('editVendor.html', Vendor=vendor, Jobs=AllJobs, warning=WarningMessage)

@application.route('/listVendors',methods=['GET'])
def list_vendors():
    global WarningMessage
    vendors = db.session.query(Vendor).all()
    
    return render_template('listVendors.html', Vendors=vendors, warning=WarningMessage)

@application.route('/createVendor',methods=['POST'])
def create_vendor():
    vendor = Vendor()
    db.session.add(vendor)

    return save_vendor_from_form(vendor, "create", request.form)

@application.route('/updateVendor',methods=['POST'])
def update_vendor():
    vendorId = request.form['vendorId']
    vendor = vendor_for_id(vendorId)

    return save_vendor_from_form(vendor, "update", request.form)

def save_vendor_from_form(vendor, action, form):
    global WarningMessage
    global AllJobs
    vendor.name = str(form['name'])
    vendor.contact = str(form['contact'])
    vendor.contact = str(form['contact'])
    vendor.phone = str(form['phone'])
    vendor.emailList = str(form['emailList'])

    jobs = jobs_from_form(form)
    vendor.jobs = jobs
    
    try :
        db.session.commit()
    	WarningMessage = "Updates saved for Vendor " + str(vendor.name)
    except Exception as ex:
        db.session.rollback()
        print str(ex)
    	WarningMessage = "Unable to " + str(action) + " Vendor " + str(vendor.name) + " " + str(ex.message)

    return render_template('editVendor.html', Vendor=vendor, Jobs=AllJobs, warning=WarningMessage)

@application.route('/removeVendorUser',methods=['GET'])
def remove_vendor_user():
    global WarningMessage
    global AllJobs
    vendorId = request.args.get('vendorId', 0, type=int)
    vendor = vendor_for_id(vendorId)
    userId = request.args.get('userId', 0, type=int)

    users = vendor.users()
    for user in users :
    	if user.id == userId :
    		user.vendorId = None
    		break

    try :
        db.session.commit()
    	WarningMessage = "Updates saved for Vendor " + str(vendor.name)
    except Exception as ex:
        db.session.rollback()
        print str(ex)
    	WarningMessage = "Unable to " + str(action) + " Vendor " + str(vendor.name) + " " + str(ex.message)
    
    return render_template('editVendor.html', Vendor=vendor, Jobs=AllJobs, warning=WarningMessage)

@application.route('/createVendorUser',methods=['POST'])
def create_vendor_user():
    global WarningMessage
    global AllJobs
    vendorId = int(request.form['vendorId'])
    vendor = vendor_for_id(vendorId)
    email = str(request.form['email'])
    user = user_for_email(email)

    if user :
    	if user.vendorId and user.vendorId != vendorId :
    		user = None
    		WarningMessage = "User " + str(email) + " is already assigned to another Vendor"
    	else :
    		WarningMessage = "User " + user.email + " successfully assigned to Vendor"
    elif email and len(email) > 0 :
    	user = User()
        db.session.add(user)
    	user.email = email
    	tmpPassword = User.tmpPassword()
    	user.setPassword(tmpPassword)
    	user.passwordRequiresReset = True
    	user.permissionId = 4
    	WarningMessage = "Created User " + user.email + " with a temporary password of " + str(tmpPassword)
    else :
    	WarningMessage = "email address is required for new users"

    if user :
    	user.vendorId = vendorId
    	user.firstName = str(request.form['firstName'])
    	user.lastName = str(request.form['lastName'])

    	try :
        	db.session.commit()
    	except Exception as ex:
        	db.session.rollback()
        	print str(ex)
    		WarningMessage = "Unable to create new user for Vendor"
    
    return render_template('editVendor.html', Vendor=vendor, Jobs=AllJobs, warning=WarningMessage)

# @application.route('/updateVendorConfig',methods=['POST'])
# def update_vendor():
#     global WarningMessage
#     vendorId = request.form['vendorId']
#     vendor = user_for_id(vendorId)
# 
#     try :
#         db.session.commit()
#     	WarningMessage = "Updates saved for Vendor " + str(vendor.name())
#     except Exception as ex:
#         db.session.rollback()
#     	print dir(ex)
#     	WarningMessage = "Unable to create update Vendor " + str(vendor.name) + " " + str(ex.message)
# 
#     return render_template('editVendorConfig.html', Vendor=vendor, Config=vendorConfig, warning=WarningMessage)

@application.route('/createUser',methods=['POST'])
def create_user():
    global WarningMessage
    global AllJobs
    global AllVendors
    userDict = session['user']
    currentPermission = int(userDict['permissionId'])
    user = User()
    user.setEmail(request.form['email'])
    user.permissionId = request.form['permissionId']
    tmpPassword = User.tmpPassword()
    user.setPassword(tmpPassword)
    user.passwordRequiresReset = True
    templateName = "newUser.html"

    if user.permissionId == '4' :
#    	user.firstName = request.form['name']
#    	templateName = "newVendor.html"
#    	if 'jobId' in request.form.keys() :
#    		vendorJobConfig = vendorJobConfig_from_form(request.form)
#    		vendorJob = job_for_id(vendorJobConfig.jobId)
#    		user.jobs = [vendorJob]
#    		db.session.add(vendorJobConfig)
#    	else :
    	WarningMessage = "Need to implement new users for Vendor"
    	return render_template(templateName, Jobs=AllJobs, warning=WarningMessage)
    else :
    	user.firstName = request.form['firstName']
    	user.lastName = request.form['lastName']
    	jobs = jobs_from_form(request.form)
    	user.jobs = jobs

    db.session.add(user)
    try :
        db.session.commit()
    	# send_email([user.email],'Welcome to CrownCorr','Your temporary password is ' + tmpPassword)
    	print 'PJC: Temporarily disabled email'
    	print 'PJC: Welcome to CrownCorr, Your temporary password is ' + tmpPassword
    	WarningMessage = "User " + str(user.email) + " has been created.   Check your email inbox for a temporary password"
    	# PJC - remove the line below after we re-enable email.
    	WarningMessage = WarningMessage + "  Temporarily disabled email.   Temporary password is " + tmpPassword
    except Exception as ex:
        db.session.rollback()
    	print dir(ex)
    	WarningMessage = "Unable to create new User " + str(user.email) + " " + str(ex.message)
        print 'Unable to save User [%s]' % str(ex)

    return render_template(templateName, UserPermission=currentPermission, Jobs=AllJobs, warning=WarningMessage)

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
    			return render_jobs_page(user)
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
    vendor = user_for_id(vendorId)
    job = job_for_id(jobId)

    return render_template('newShipment.html', Shipment=shipment, Vendor=vendor, Job=job)

@application.route('/editShipment',methods=['POST'])
def edit_shipment():
    shipmentId = request.form['shipmentId']
    shipment = shipment_for_id(shipmentId)
    job = job_for_id(shipment.jobId)
    vendor = user_for_id(shipment.vendorId)

    return render_template('editShipment.html', Vendor=vendor, Job=job, Shipment=shipment, Photos=shipment.photos)

@application.route('/createShipment',methods=['POST'])
def create_shipment():
    shipment = Shipment()
    jobId = request.form['jobId']
    vendorId = request.form['vendorId']
    shipment.jobId = jobId
    shipment.vendorId = vendorId

    update_shipment_from_form(shipment, request.form)
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
    	# Sometimes the new Object did not make it in to the Session.
    	if None == user :
                db.session.expire_all()
                db.session.commit()
                user = db.session.query(User).filter_by(email=email.lower()).first()
    except Exception as ex :
        db.session.rollback()
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
                                	# Synch up the Shipment object.
                                	shipment = shipment_for_id(shipment.id)
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
    			# Refresh the Shipment.   We had problems with photos
    			# hanging around after they were deleted.
    			db.session.expire(shipment)
    			db.session.commit()
    			shipment = shipment_for_id(shipmentId)
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
	application.run(debug=True,host='0.0.0.0',port=8888)
	# application.run(debug=True,host='172.20.10.4',port=9999)

