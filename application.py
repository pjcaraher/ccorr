import os
import config
import sys
import json
import jwt
import re
import jwt
import boto3
import botocore
from botocore.exceptions import ClientError
import base64
import hashlib
import tempfile
from datetime import datetime
from werkzeug. utils import secure_filename
from sqlalchemy import or_

from flask import Flask, request, session, flash, url_for, redirect, \
     render_template, abort, send_from_directory, Response
from application.models import User, Job, Shipment, ShipmentPhoto, ShipmentComment, Vendor, JobMap
from application import db
from application import apUtils
from threading import Thread

application = Flask(__name__)
application.config.from_object('config')
db.init_app(application)

# ONLY turn this on when testing.   Otherwise, it cause problems with DB Session timeouts.
#     application.debug=True
application.secret_key = '3915408C-CFCC-47D4-86B4-E2A2819804B6'

AllJobs = []
AllVendors = []
WarningMessage = ""
MobileTTL = 60 * 60
ERR_NONE = 100
ERR_NO_USER = 101
ERR_CALL_FAILED = 102
ERR_NO_SHIPMENT = 103

IMAGE_DIR = "/static/images/"

def user_for_id(userId) :
    user = None

    try :
    	user = db.session.query(User).filter(User.isHidden == 0).filter_by(id=userId).first()
    	# Sometimes the new Object did not make it in to the Session.
    	if None == user :
                db.session.expire_all()
                db.session.commit()
                user = db.session.query(User).filter(User.isHidden == 0).filter_by(id=userId).first()
    except Exception as ex :
        db.session.rollback()
    	print 'Exception fetching user id [' + str(userId) + '] ' + str(ex)
    	user = None

    return user

def user_for_email(email) :
    user = None

    try :
    	user = db.session.query(User).filter(User.isHidden == 0).filter(User.email.ilike(email)).first()
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

def map_for_id(mapId) :
    map = None

    try :
    	map = db.session.query(JobMap).filter_by(id=mapId).first()
    	# Sometimes the new Object did not make it in to the Session.
    	if None == map :
                db.session.expire_all()
                db.session.commit()
                map = db.session.query(JobMap).filter_by(id=mapId).first()
    except Exception as ex :
        db.session.rollback()
    	map = None
    	print 'Exception fetching map for id [' + str(mapId) + '] = ' + str(ex)

    return map

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

def mapIds_from_form(form) :
    mapIds = []

    for key in form.keys() :
    	if key.startswith("mapId_") :
    		mapId = key[6:]
    		mapIds.append(mapId)

    return mapIds

def maps_from_form(form) :
    mapIds = mapIds_from_form(form)
    maps = []

    for mapId in mapIds:
    	map = map_for_id(mapId)
    	maps.append(map)

    return maps

def form_bool_for_key(form, key) :
    torf = False

    if key in form.keys() :
	if form[key].lower() == 'on' :
    		torf = True

    return torf

def updateUser_from_form(user, form) :
    user.firstName = form['firstName']
    user.lastName = form['lastName']
    user.email = form['email']
    user.permissionId = request.form['permissionId']
    jobs = jobs_from_form(form)
    user.jobs = jobs

    return user

def users_visible_to_user(user, job) :
    users = []
    if user.hasPermission(config.PERMISSION_ADMIN) :  # If we are Admin
    	users = db.session.query(User).filter(User.isHidden == 0).filter(or_(User.permissionId == config.PERMISSION_PM, User.permissionId == config.PERMISSION_FS)).all()
    elif user.hasPermission(config.PERMISSION_PM) :  # If we are Project Manager
    	dbUsers = db.session.query(User).filter(User.isHidden == 0).filter(or_(User.permissionId == config.PERMISSION_PM, User.permissionId == config.PERMISSION_FS)).all()
    	for _u in dbUsers :
    		if _u.hasJob(job) :
    			users.append(_u)

    return users

def parse_password(password):
    minPasswordSize = 4
    if len(password) < minPasswordSize :
	raise Exception("Passwords must be at least " + str(minPasswordSize) + " characters long")

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
    job.showDriverName = form_bool_for_key(form,'showDriverName')
    job.showDriverPhone = form_bool_for_key(form,'showDriverPhone')
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
    if "driverName" in form.keys() :
    	shipment.driverName = stringForShipmentKey("driverName", form)
    if "driverPhone" in form.keys() :
    	shipment.driverPhone = stringForShipmentKey("driverPhone", form)

    return

def save_shipment(shipment, request):
    global WarningMessage
    completedShipments = []
    openShipments = []
    try :
    	shippedDate = date_with_prefix('shipped_', request.form)
    	shipment.shippedDate = shippedDate
    except :
    	print "No shipmentDate"
    
    try :
    	expectedDate = date_with_prefix('expected_', request.form)
    	shipment.expectedDate = expectedDate
    except :
    	print "No expectedDate"

    try :
    	arrivalDate = date_with_prefix('arrival_', request.form)
    	shipment.arrivalDate = arrivalDate
    except :
    	print "No arrivalDate"

    maps = maps_from_form(request.form)
    comment = None

    shipment.maps = maps

    if 'comment' in request.form.keys() :
    	if len(request.form['comment']) > 0 :
    		userDict = session['user']
    		if userDict:
    			user = user_for_id(userDict['id'])
    		if user :
    			comment = request.form['comment']
    			shipmentComment = ShipmentComment()
                	shipmentComment.shipmentId = shipment.id
                	shipmentComment.comment = comment
                	shipmentComment.commentDate = datetime.now()
                	shipmentComment.userId = user.id
                	db.session.add(shipmentComment)
    		else :
                	print "Error adding Comment.   There is no logged in User."


    try :
        db.session.commit()
        WarningMessage = "Delivery Updated"
    except Exception as ex:
        db.session.rollback()
        WarningMessage = "Failed to Update Delivery"
        print 'Unable to save Shipment [%s]' % str(ex)

    vendor = vendor_for_id(shipment.vendorId)
    job = job_for_id(shipment.jobId)
    userDict = session['user']
    user = None

    if userDict:
    	user = user_for_id(userDict['id'])

    for shipment in job.shipments :
    	if shipment.arrivalDate :
    		completedShipments.append(shipment)
    	else :
    		openShipments.append(shipment)

    return render_template('displayJob2.html', Job=shipment.job, OpenShipments=openShipments, CompletedShipments=completedShipments, User=user, warning=WarningMessage, Years=years_to_display())

def save_job_map(mapName, s3Key, type, job) :
    global WarningMessage
    map = JobMap()
    map.name = mapName
    map.s3Key = s3Key
    map.type = type
    map.jobId = job.id

    db.session.add(map)
    try :
        db.session.commit()
    	WarningMessage = map.name + " was successfully created"
    except Exception as ex:
        db.session.rollback()
    	WarningMessage = "Unable to create new Job " + str(ex.message)
        print 'Unable to create Job [%s]' % str(ex)

    return map.id

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
	if user.hasPermission(config.PERMISSION_ADMIN) :  # If we are Admin
		jobs = AllJobs
	elif user.hasPermission(config.PERMISSION_FS) :  # If we are a PM or FS
		jobs = user.jobs
	elif user.hasPermission(config.PERMISSION_VENDOR) :  # If we are a Vendor
		vendor = vendor_for_id(user.vendorId)
		if vendor :
			jobs = vendor.jobs

		if len(jobs) == 1 :
			session['jobId'] = jobs[0].id
			return render_job_page()
		else :
    			return render_template('listJobs2.html', Jobs=jobs, User=user)

    # return render_template('pmMainPage.html', Jobs=jobs, User=user)
    return render_template('listJobs2.html', Jobs=jobs, User=user)

def render_job_page():
    global WarningMessage
    job = job_for_id(session['jobId'])
    shipments = job.shipments
    shipments.sort()
    openShipments = []
    completedShipments = []
    userDict = session['user']
    user = None

    if userDict:
    	user = user_for_id(userDict['id'])

    	if user.permissionId == config.PERMISSION_VENDOR :  # If we are a Vendor show only our Deliveries
    		for shipment in reversed(shipments):
    			if shipment.vendorId != user.vendorId :
    				shipments.remove(shipment)

    for shipment in shipments :
    	if shipment.arrivalDate :
    		completedShipments.append(shipment)
    	else :
    		openShipments.append(shipment)

    return render_template('displayJob2.html', Job=job, OpenShipments=openShipments, CompletedShipments=completedShipments, User=user, Years=years_to_display(), warning=WarningMessage)

def years_to_display() :
    years = []
    today = str(datetime.now())
    curr_year = int(today[:4])

    years.append(curr_year - 1)
    years.append(curr_year)
    years.append(curr_year + 1)
    years.append(curr_year + 2)

    return years

def new_user_email_tmppass(user, tmpPassword) :
    print 'PJC: Welcome to CrownCorr, Your temporary password is ' + tmpPassword

    subject = "Welcome to the Crown Corr Delivery App"
    recipient = user.email

    if (user.permissionId == config.PERMISSION_FS) :
	with open ("templates/new_fieldstaff_email.txt", "r") as myfile:
		text=myfile.read()
	text = text.replace("<MOBILEDOWNLOADURL>",os.environ['MOBILEDOWNLOADURL'])
	text = text.replace("<USEREMAIL>",str(user.email))
	text = text.replace("<PASSWORD>",tmpPassword)
	with open ("templates/new_fieldstaff_email.html", "r") as myfile:
		html=myfile.read()
	html = html.replace("<MOBILEDOWNLOADURL>",os.environ['MOBILEDOWNLOADURL'])
	html = html.replace("<USEREMAIL>",str(user.email))
	html = html.replace("<PASSWORD>",tmpPassword)
    	send_ses(recipient, subject, text, html)
    else :
	with open ("templates/new_webuser_email.txt", "r") as myfile:
		text=myfile.read()
	text = text.replace("<BASEURL>",os.environ['BASEURL'])
	text = text.replace("<USERID>",str(user.id))
	text = text.replace("<PASSWORD>",tmpPassword)
	with open ("templates/new_webuser_email.html", "r") as myfile:
		html=myfile.read()
	html = html.replace("<BASEURL>",os.environ['BASEURL'])
	html = html.replace("<USERID>",str(user.id))
	html = html.replace("<PASSWORD>",tmpPassword)
    	send_ses(recipient, subject, text, html)
    return

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
    	AllVendors = db.session.query(User).filter(User.isHidden == 0).filter_by(permissionId=config.PERMISSION_VENDOR)
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
    	elif request.endpoint == 'new_user_reset' :
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
    userDict = session['user']
    user = None

    if userDict:
    	user = user_for_id(userDict['id'])
    
    if user == None :
    	WarningMessage = ""
    	return render_template('loginUser.html', warning=WarningMessage)
    else :
    	return render_template('listJobs2.html', Jobs=AllJobs, User=user)

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
    	user = db.session.query(User).filter(User.isHidden == 0).filter_by(email=email.lower()).first()
    	# Sometimes the new Object did not make it in to the Session.
    	if None == user :
                db.session.expire_all()
                db.session.commit()
                user = db.session.query(User).filter(User.isHidden == 0).filter_by(email=email.lower()).first()
    except Exception as ex1 :
        db.session.rollback()
        # Try again.
        try :
    		sys.stderr.write('Try second login for ' + str(email))
    		user = db.session.query(User).filter(User.isHidden == 0).filter_by(email=email.lower()).first()
        except Exception as ex :
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
def select_job(jobId):
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

def send_ses(recipient, subject, text, html=None) :
    # Replace sender@example.com with your "From" address.
    # This address must be verified with Amazon SES.
    SENDER = "ccorr@mustangdm.com"

    # Replace recipient@example.com with a "To" address. If your account 
    # is still in the sandbox, this address must be verified.
    RECIPIENT = recipient
    if os.environ['EMAIL_SANDBOX'] == "TRUE" :
    	RECIPIENT = "pj@mustangdm.com"

    # Specify a configuration set. If you do not want to use a configuration
    # set, comment the following variable, and the 
    # ConfigurationSetName=CONFIGURATION_SET argument below.
    CONFIGURATION_SET = "ConfigSet"

    # If necessary, replace us-west-2 with the AWS Region you're using for Amazon SES.
    AWS_REGION = "us-west-2"

    # The subject line for the email.
    SUBJECT = "Welcome to the Crown Corr app"

    # The email body for recipients with non-HTML email clients.
    BODY_TEXT = text
            
    # The HTML body of the email.
    BODY_HTML = html

    # The character encoding for the email.
    CHARSET = "UTF-8"

    # Create a new SES resource and specify a region.
    client = boto3.client('ses',region_name=AWS_REGION)
    
    MESSAGE = None

    # Try to send the email.
    try:
        if BODY_HTML :
            	MESSAGE={
                	'Body': {
                    		'Text': {
                        		'Charset': CHARSET,
                        		'Data': BODY_TEXT,
                    		},
                    		'Html': {
                        		'Charset': CHARSET,
                        		'Data': BODY_HTML,
                    		}
                	},
                	'Subject': {
                    		'Charset': CHARSET,
                    		'Data': SUBJECT,
                	},
            	}
        else :
            	MESSAGE={
                	'Body': {
                    		'Text': {
                        		'Charset': CHARSET,
                        		'Data': BODY_TEXT,
                    		}
                	},
                	'Subject': {
                    		'Charset': CHARSET,
                    		'Data': SUBJECT,
                	},
            	}

        response = client.send_email(
            Destination={
                'ToAddresses': [
                    RECIPIENT,
                ],
            },
            Message=MESSAGE,
            Source=SENDER
            # If you are not using a configuration set, comment or delete the
            # following line
            # ConfigurationSetName=CONFIGURATION_SET,
        )
    # Display an error if something goes wrong.	
    except ClientError as e:
        print(e.response['Error']['Message'])
    else:
        print("Email sent! Message ID:"),
        print(response['MessageId'])

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
    job.street = request.form['street']
    job.city = request.form['city']
    job.state = request.form['state']
    job.zip = request.form['zip']
    job.instructions = request.form['instructions']
    userDict = session['user']
    user = None
    jobs = None

    update_jobConfig_from_form(job, request.form)

    if userDict:
    	user = user_for_id(userDict['id'])

    db.session.add(job)
    try :
        db.session.commit()
    	AllJobs = db.session.query(Job).all()
    	WarningMessage = job.name + " was successfully created"
    	session['jobId'] = job.id
    except Exception as ex:
        db.session.rollback()
    	WarningMessage = "Unable to create new Job " + str(ex.message)
        print 'Unable to create Job [%s]' % str(ex)

    if user :
    	if user.permissionId <= config.PERMISSION_ADMIN :
    		jobs = AllJobs
    	else :
    		jobs = user.jobs

    return render_template("listJobs2.html", User=user, Jobs=jobs, warning=WarningMessage)

@application.route('/updateJob',methods=['POST'])
def update_job():
    global WarningMessage
    global AllJobs
    jobId = request.form['jobId']
    job = job_for_id(jobId)
    if 'name' in request.form.keys() :
    	job.name = request.form['name']
    if 'number' in request.form.keys() :
    	job.number = request.form['number']
    if 'street' in request.form.keys() :
    	job.street = request.form['street']
    if 'city' in request.form.keys() :
    	job.city = request.form['city']
    if 'state' in request.form.keys() :
    	job.state = request.form['state']
    if 'zip' in request.form.keys() :
    	job.zip = request.form['zip']
    if 'instructions' in request.form.keys() :
    	job.instructions = request.form['instructions']
    userDict = session['user']
    jobs = None
    user = None
    maps = maps_from_form(request.form)

    update_jobConfig_from_form(job, request.form)

    for map in maps :
    	map.deleted = True

    if userDict:
    	user = user_for_id(userDict['id'])

    try :
        db.session.commit()
    	WarningMessage = job.name + " was successfully updated"
    except Exception as ex:
        db.session.rollback()
    	WarningMessage = "Unable to update Job " + str(ex.message)
        print 'Unable to update Job [%s]' % str(ex)

    if user :
    	if user.permissionId <= config.PERMISSION_ADMIN :
    		jobs = AllJobs
    	else :
    		jobs = user.jobs

    return render_template("listJobs2.html", User=user, Jobs=jobs, warning=WarningMessage)

@application.route('/newUser',methods=['POST','GET'])
def new_user():
    global WarningMessage
    global AllJobs
    userDict = session['user']
    currentPermission = int(userDict['permissionId'])
    
    return render_template('newUser.html', UserPermission=currentPermission, User=userDict, Jobs=AllJobs, warning=WarningMessage)

@application.route('/newVendor',methods=['GET'])
def new_vendor():
    global WarningMessage
    global AllJobs
    userDict = session['user']
    
    return render_template('newVendor.html', Jobs=AllJobs, User=userDict, warning=WarningMessage)

@application.route('/editVendor',methods=['GET'])
def edit_vendor():
    global WarningMessage
    global AllJobs
    vendorId = request.args.get('vendorId', 0, type=int)
    vendor = vendor_for_id(vendorId)
    userDict = session['user']
    
    return render_template('editVendor.html', Vendor=vendor, User=userDict, Jobs=AllJobs, warning=WarningMessage)

@application.route('/listVendors',methods=['GET'])
def list_vendors():
    global WarningMessage
    global AllJobs
    vendors = db.session.query(Vendor).all()
    userDict = session['user']
    
    return render_template('listVendors2.html', Jobs=AllJobs, User=userDict, Vendors=vendors, warning=WarningMessage)

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
    userDict = session['user']
    submittedName = str(form['name'])

    jobs = jobs_from_form(form)
    vendor.jobs = jobs
    vendors = db.session.query(Vendor).all()
    
    if submittedName and len(submittedName) > 0 :
    	vendor.name = submittedName
    	vendor.contact = str(form['contact'])
    	vendor.phone = str(form['phone'])
    	vendor.emailList = str(form['emailList'])

    	try :
        	db.session.commit()
    		WarningMessage = "Updates saved for " + str(vendor.name)
    	except Exception as ex:
        	db.session.rollback()
        	print str(ex)
    else :
        db.session.rollback()
    	WarningMessage = "Name is required for Vendor"

    return render_template('listVendors2.html', Vendors=vendors, User=userDict, Jobs=AllJobs, warning=WarningMessage)

@application.route('/removeVendorUser',methods=['GET'])
def remove_vendor_user():
    global WarningMessage
    global AllJobs
    vendorId = request.args.get('vendorId', 0, type=int)
    vendor = vendor_for_id(vendorId)
    userId = request.args.get('userId', 0, type=int)
    userDict = session['user']
    vendors = db.session.query(Vendor).all()

    users = vendor.users()
    for user in users :
    	if user.id == userId :
    		user.isHidden = 1
    		break

    try :
        db.session.commit()
    	WarningMessage = "Updates saved for Vendor " + str(vendor.name)
    except Exception as ex:
        db.session.rollback()
        print str(ex)
    	WarningMessage = "Unable to " + str(action) + " Vendor " + str(vendor.name) + " " + str(ex.message)
    
    return render_template('listVendors2.html', Vendors=vendors, User=userDict, Jobs=AllJobs, warning=WarningMessage)

@application.route('/createVendorUser',methods=['POST'])
def create_vendor_user():
    global WarningMessage
    global AllJobs
    tmpPassword = None
    userDict = session['user']
    vendorId = int(request.form['vendorId'])
    vendor = vendor_for_id(vendorId)
    email = str(request.form['email'])
    user = user_for_email(email)
    vendors = db.session.query(Vendor).all()

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
    	user.permissionId = config.PERMISSION_VENDOR
    	WarningMessage = "Created User " + user.email + " with a temporary password of " + str(tmpPassword)
    else :
    	WarningMessage = "email address is required for new users"

    if user :
    	user.vendorId = vendorId
    	user.firstName = str(request.form['firstName'])
    	user.lastName = str(request.form['lastName'])

    	try :
        	db.session.commit()
        	new_user_email_tmppass(user, tmpPassword)
    	except Exception as ex:
        	db.session.rollback()
        	print str(ex)
    		WarningMessage = "Unable to create new user for Vendor"
    
    return render_template('listVendors2.html', Vendors=vendors, User=userDict, Jobs=AllJobs, warning=WarningMessage)

# @application.route('/updateVendorConfig',methods=['POST'])
# def update_vendor():
#     global WarningMessage
#     vendorId = request.form['vendorId']
#     vendor = vendor_for_id(vendorId)
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

@application.route('/listUsers',methods=['GET'])
def list_users():
    global WarningMessage
    global AllJobs
    users = []

    userDict = session['user']
    user = None

    if userDict:
    	user = user_for_id(userDict['id'])

    job = None
    if user.hasPermission(config.PERMISSION_ADMIN) :  # If we are Admin
    	users = users_visible_to_user(user, job)
    else :
    	try :
    		job = user.jobs[0]
    		users = users_visible_to_user(user, job)
    	except Exception as e :
	     	WarningMessage = "A job needs to be specified."
    
    return render_template('listUsers2.html', User=user, Users=users, Jobs=AllJobs, warning=WarningMessage)

@application.route('/updateUser',methods=['POST'])
def update_user():
    global WarningMessage
    global AllJobs
    users = []
    userId = request.form['userId']
    userDict = session['user']
    user = None

    if userDict:
    	user = user_for_id(userDict['id'])

    userToUpdate = user_for_id(userId)
    if userToUpdate :
    	updateUser_from_form(userToUpdate, request.form)

    job = None
    if user.hasPermission(config.PERMISSION_ADMIN) :  # If we are Admin
    	users = users_visible_to_user(user, job)
    else :
    	try :
    		job = user.jobs[0]
    		users = users_visible_to_user(user, job)
    	except Exception as e :
	     	WarningMessage = "A job needs to be specified."

    try :
        db.session.commit()
    	WarningMessage = "User " + str(userToUpdate.email) + " updated."
    except Exception as ex:
        db.session.rollback()
    	print dir(ex)
    	WarningMessage = "Unable to update User " + str(user.email) + " " + str(ex.message)
    
    return render_template('listUsers2.html', User=user, Users=users, Jobs=AllJobs, warning=WarningMessage)

@application.route('/createUser',methods=['POST'])
def create_user():
    global WarningMessage
    global AllJobs
    global AllVendors
    users = []
    userId = request.form['userId']
    userDict = session['user']
    user = None
    currentPermission = int(userDict['permissionId'])
    newUser = User()
    newUser.setEmail(request.form['email'])
    newUser.permissionId = request.form['permissionId']
    tmpPassword = User.tmpPassword()
    newUser.setPassword(tmpPassword)
    newUser.passwordRequiresReset = True
    templateName = "newUser.html"

    if userDict:
    	user = user_for_id(userDict['id'])

    if int(newUser.permissionId) == config.PERMISSION_VENDOR :
#    	newUser.firstName = request.form['name']
#    	templateName = "newVendor.html"
#    	if 'jobId' in request.form.keys() :
#    		vendorJobConfig = vendorJobConfig_from_form(request.form)
#    		vendorJob = job_for_id(vendorJobConfig.jobId)
#    		newUser.jobs = [vendorJob]
#    		db.session.add(vendorJobConfig)
#    	else :
    	WarningMessage = "Need to implement new users for Vendor"
    	return render_template(templateName, Jobs=AllJobs, warning=WarningMessage)
    else :
    	newUser.firstName = request.form['firstName']
    	newUser.lastName = request.form['lastName']
    	jobs = jobs_from_form(request.form)
    	newUser.jobs = jobs

    db.session.add(newUser)
    try :
        db.session.commit()
    	WarningMessage = "User " + str(newUser.email) + " has been created.   Check your email inbox for a temporary password"
    	new_user_email_tmppass(newUser, tmpPassword)
    except Exception as ex:
        db.session.rollback()
    	print dir(ex)
    	WarningMessage = "Unable to create new User " + str(newUser.email) + " " + str(ex.message)
        print 'Unable to save User [%s]' % str(ex)

    job = None
    if user.hasPermission(config.PERMISSION_ADMIN) :  # If we are Admin
    	users = users_visible_to_user(user, job)
    else :
    	try :
    		job = user.jobs[0]
    		users = users_visible_to_user(user, job)
    	except Exception as e :
	     	WarningMessage = "A job needs to be specified."

    return render_template('listUsers2.html', User=user, Users=users, Jobs=AllJobs, warning=WarningMessage)

@application.route('/resendNewUserEmail',methods=['POST'])
def resend_newuser_email():
    global WarningMessage
    global AllJobs
    global AllVendors
    users = []
    user = None
    userId = request.form['userId']
    userDict = session['user']
    currentPermission = int(userDict['permissionId'])
    newUser = user_for_id(userId)
    tmpPassword = User.tmpPassword()
    newUser.setPassword(tmpPassword)
    newUser.passwordRequiresReset = True
    templateName = "newUser.html"

    if userDict:
    	user = user_for_id(userDict['id'])

    try :
        db.session.commit()
    	WarningMessage = "New User email re-sent to " + str(newUser.email) + ".   Check your email inbox (and Spam folder) for a temporary password."
    	new_user_email_tmppass(newUser, tmpPassword)
    except Exception as ex:
        db.session.rollback()
    	print dir(ex)
    	WarningMessage = "Unable to resend invite to User " + str(newUser.email) + " " + str(ex.message)
        print 'Unable to resend invite to User [%s]' % str(ex)

    job = None
    if user.hasPermission(config.PERMISSION_ADMIN) :  # If we are Admin
    	users = users_visible_to_user(user, job)
    else :
    	try :
    		job = user.jobs[0]
    		users = users_visible_to_user(user, job)
    	except Exception as e :
	     	WarningMessage = "A job needs to be specified."

    return render_template('listUsers2.html', User=user, Users=users, Jobs=AllJobs, warning=WarningMessage)

@application.route('/resetPassword',methods=['POST'])
def reset_password():
    global WarningMessage
    userId = request.form['userId']

    user = user_for_id(userId)
    if user :
    	oldPassword = request.form['oldPassword']
    	if user.passwordsMatch(oldPassword) :
    		password = request.form['password']
    		try :
    			parse_password(password)
    			user.setPassword(password)
    		except Exception as ex:
    			WarningMessage = str(ex)
    			return render_template('resetPassword.html', user=user.asDict(), oldPassword=oldPassword, warning=WarningMessage)

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

@application.route('/newUserReset',methods=['GET'])
def new_user_reset():
    global WarningMessage
    # http://site/newUserReset?userId=1&temp=password
    userId = request.args.get('userId', 0, type=int)
    tmpPassword = request.args.get('temp', 0, type=str)

    user = user_for_id(userId)
    if user :
    	if user.passwordsMatch(tmpPassword) :
    		session['user'] = user.asDict()
    		return render_template('resetPassword.html', user=user.asDict(), oldPassword=tmpPassword, warning=WarningMessage)
    	else :
    		WarningMessage = "Temporary Password has expired."
    		session['user'] = None
    		return render_template('loginUser.html', warning=WarningMessage)
    else :
    	# If there is no user in the URL then simply direct to the login page.
    	session['user'] = None
    	return render_template('loginUser.html', warning=WarningMessage)

@application.route('/hideUser',methods=['POST'])
def hide_user():
    global WarningMessage
    global AllJobs
    users = []
    user = None
    userToHide = None
    userDict = session['user']
    idForUserToHide = request.form['userId']

    if userDict:
    	user = user_for_id(userDict['id'])

    userToHide = user_for_id(idForUserToHide)
    if userToHide :
    	try :
        	userToHide.isHidden = 1
        	db.session.commit()
    	except Exception as ex:
        	db.session.rollback()
    		print dir(ex)
    		WarningMessage = "Unable to remove User " + str(userToHid.email) + " " + str(ex.message)
        	print 'Unable to set isHidden for User [%s]' % str(ex)
    else :
    	# If there is no user print warning
    	WarningMessage = "No user was defined"

    job = None
    if user.hasPermission(config.PERMISSION_ADMIN) :  # If we are Admin
    	users = users_visible_to_user(user, job)

    return render_template('listUsers2.html', User=user, Users=users, Jobs=AllJobs, warning=WarningMessage)

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
    job = job_for_id(shipment.jobId)
    vendor = vendor_for_id(shipment.vendorId)
    userDict = session['user']
    user = None

    if userDict:
    	user = user_for_id(userDict['id'])

    return render_template('editShipment.html', User=user, Vendor=vendor, Job=job, Shipment=shipment, Photos=shipment.photos)

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
    update_shipment_from_form(shipment, request.form)

    return save_shipment(shipment, request)

@application.route('/printShipment',methods=['GET'])
def print_shipment() :
    shipmentId = request.args.get('shipmentId', 0, type=int)
    shipment = None
    vendor = None
    job = None

    if shipmentId :
    	shipment = shipment_for_id(shipmentId)

    if shipment :
    	vendor = vendor_for_id(shipment.vendorId)
    	job = job_for_id(shipment.jobId)

    return render_template('printShipment.html', Shipment=shipment, Vendor=vendor, Job=job)

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
    	user = db.session.query(User).filter(User.isHidden == 0).filter_by(email=email.lower()).first()
    	# Sometimes the new Object did not make it in to the Session.
    	if None == user :
                db.session.expire_all()
                db.session.commit()
                user = db.session.query(User).filter(User.isHidden == 0).filter_by(email=email.lower()).first()
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

@application.route('/mResetUserPassword',methods=['POST'])
def mobile_reset_user_password():
    dict = json.loads(str(request.data))
    user = None
    email = dict['email']
    oldPassword = dict['oldPassword']
    password = dict['password']
    error = None
    status = ERR_NO_USER
    retVal = {}

    try :
    	user = db.session.query(User).filter(User.isHidden == 0).filter_by(email=email.lower()).first()
    	# Sometimes the new Object did not make it in to the Session.
    	if None == user :
                db.session.expire_all()
                db.session.commit()
                user = db.session.query(User).filter(User.isHidden == 0).filter_by(email=email.lower()).first()
    except Exception as ex :
        db.session.rollback()
    	print 'Exception fetching User id [' + str(email) + '] ' + str(ex)
    	user = None

    if None == user :
    	error = "No user for email " + str(email)
    else :
    	if user.passwordsMatch(oldPassword) :
    		try :
    			parse_password(password)
    			user.setPassword(password)
    			user.passwordRequiresReset = False
    			db.session.commit()
    			retVal['access_token'] = jwt_for_user(user)
    			retVal['user'] = str(user.asDict())
    			status = ERR_NONE
    		except Exception as ex:
    			error = str(ex)
    			print str(ex)
    	else :
    		error = "Password is incorrect."

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
    				db.session.refresh(shipment)
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

@application.route('/mPostComment',methods=['POST'])
def mobile_post_comment() :
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
                	shipmentComment = ShipmentComment()
                        shipmentComment.shipmentId = shipment.id
                        shipmentComment.comment = dict['comment']
                        shipmentComment.commentDate = datetime.now()
                        shipmentComment.userId = user.id
                        try :
                        	db.session.add(shipmentComment)
                                db.session.commit()
                                # Synch up the Shipment object.
                                shipment = shipment_for_id(shipment.id)
                                retVal['id'] = shipmentComment.id
                                status = ERR_NONE
                        except Exception as ex:
                                db.session.rollback()
                                print 'Unable to save ShipmentComment [%s]' % str(ex)
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

                                hasher = hashlib.md5()
                                hasher.update(image_64_decode)
    				hashName = 'photos/' + hasher.hexdigest() + '.jpg'

    				s3 = boto3.resource('s3')
    				bucketName = os.environ['S3BUCKET']
    				success = False

    				try:
    					s3.Object(bucketName, hashName).load()
    					success = True
    				except botocore.exceptions.ClientError as e:
    					if e.response['Error']['Code'] == "404":
    						# The object does not exist.
    						try :
    							result = s3.Bucket(bucketName).put_object(Key=hashName, Body=image_64_decode)
    							# Response Syntax for put_object
    							# {
    							# 	'Expiration': 'string',
    							# 	'ETag': 'string',
    							# 	'ServerSideEncryption': 'AES256'|'aws:kms',
    							# 	'VersionId': 'string',
    							# 	'SSECustomerAlgorithm': 'string',
    							# 	'SSECustomerKeyMD5': 'string',
    							# 	'SSEKMSKeyId': 'string',
    							# 	'RequestCharged': 'requester'
    							# }
    							success = True
    						except Exception as putObjectEx :
    							print "Exception while saving photo to S3 Bucket: " + str(putObjectEx)
    				except Exception as ex :
    					print "Exception while loading photo from S3 Bucket: " + str(ex)

    				if success:
    					shipmentPhoto = ShipmentPhoto()
    					shipmentPhoto.shipment = shipment
    					shipmentPhoto.s3Key = hashName
    					shipmentPhoto.photoDate = datetime.now()
    					try :
    						db.session.add(shipmentPhoto)
    						db.session.commit()
    						# Synch up the Shipment object.
    						shipment = shipment_for_id(shipment.id)
    						db.session.refresh(shipment)
    						status = ERR_NONE
    						retVal['shipmentPhoto'] = shipmentPhoto.asDict()
    					except Exception as ex:
    						db.session.rollback()
    						print 'Unable to save ShipmentPhoto [%s]' % str(ex)
    					else:
    						# Something else has gone wrong.
    						print 'Error Saving Shipment ' + str(e)
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

@application.route('/mFetchCommentsForShipment',methods=['POST'])
def mobile_fetch_comments_for_shipment():
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
    			comments = []
    			for comment in shipment.comments :
    				commentDict = comment.asDict()
    				comments.append(commentDict)
    			retVal['comments'] = comments
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
    	print 'Exception in mobile_delete_shipment_photo : ' + error
    	status = ERR_NO_USER

    retVal['status'] = status
    retVal['error'] = error

    return Response(json.dumps(retVal),  mimetype='application/json')

@application.route('/deleteMap',methods=['POST'])
def delete_map():
    global WarningMessage
    mapId = request.args.get('mapId', 0, type=int)
    mapId = request.form['mapId']
    map = map_for_id(mapId)

    if map :
    	# For some reason, the session's jobId is being cleared.  Reset it.
    	session['jobId'] = map.jobId
    	try :
    		map.deleted = True
    		db.session.commit()
    		WarningMessage = "Map Deleted"
    	except Exception as ex:
    		db.session.rollback()
    		print ex
    		WarningMessage = "Unable to delete Map"
    else :
    	WarningMessage = "No Map for MapId " + str(mapId)

    return render_job_page()

@application.route("/upload/<inputFilename>", methods=["POST", "PUT"])
def assign_map_to_job(inputFilename) :
    job = job_for_id(session['jobId'])
    mapName = request.form['mapName']
    file = request.files['file']
    fileExtension = None

    if file.filename:
    	# See if we have a file extension
    	fileParts = file.filename.split('.')
    	if len(fileParts) > 1 :
    		fileExtension = fileParts.pop()

    if file.filename:
    	if len(mapName) <= 0 :
    		mapName = file.filename
    	s3Key = upload_map_file(file, fileExtension)
    	mapId = save_job_map(mapName, s3Key, fileExtension, job)
    else :
    	print "no file name"

    userDict = session['user']
    user = None

    if userDict:
    	user = user_for_id(userDict['id'])

    return render_job_page()

def upload_map_file(fileStorage, fileExtension) :
    return upload_s3_file(fileStorage, 'maps/', fileExtension)

def upload_s3_file(fileStorage, bucket, fileExtension) :
    # Store the file for reading
    fileFullPath = os.path.join(application.config['UPLOAD_FOLDER'], fileStorage.filename)
    fileStorage.save(fileFullPath)

    # Create a hash key and store to S3
    BLOCKSIZE = 65536
    hasher = hashlib.md5()
    dataForHash = open(fileFullPath, 'rb')
    buf = dataForHash.read(BLOCKSIZE)
    while len(buf) > 0:
        hasher.update(buf)
        buf = dataForHash.read(BLOCKSIZE)
    dataForHash.close()
    hashName = bucket + hasher.hexdigest() + '.' + fileExtension
    bucketName = os.environ['S3BUCKET']

    s3 = boto3.resource('s3')
    success = False
    global WarningMessage

    try:
    	s3.Object(bucketName, hashName).load()
    except botocore.exceptions.ClientError as e:
    	if e.response['Error']['Code'] == "404":
    		# The object does not exist.
    		data = open(fileFullPath, 'rb')
    		result = s3.Bucket(bucketName).put_object(Key=hashName, Body=data)
    		data.close()
    	else:
    		# Something else has gone wrong.
    		WarningMessage = "Error saving file."
    		print 'Error Saving File ' + str(e)
    except Exception as ex :
    	WarningMessage = "Error saving file."
    	print "Exception while saving file " + hashName + " to S3 Bucket: " + str(ex)

    os.remove(fileFullPath)
    return hashName

@application.route("/uploadPhoto", methods=["POST", "PUT"])
def assign_photo_to_shipment() :
    global WarningMessage
    shipmentId = request.form['shipmentId']
    shipment = shipment_for_id(shipmentId)
    file = request.files['file']
    retVal = {}

    if file :
    	s3Key = upload_photo_file(file)
    	retVal = save_shipment_photo(s3Key, shipment)
    else :
    	retVal['status'] = ERR_NONE
    	print "no file name"

    if ERR_NONE == retVal['status'] :
    	WarningMessage = "Error saving photo"
    else :
    	WarningMessage = "Successfully uploaded photo"

    return render_job_page()

def upload_photo_file(fileStorage) :
    return upload_s3_file(fileStorage, 'photos/', 'jpg')

def save_shipment_photo(hashName, shipment) :
    status = ERR_NONE
    error = ""
    retVal = {}

    try :
    	if shipment :
    		shipmentPhoto = ShipmentPhoto()
    		shipmentPhoto.shipment = shipment
    		shipmentPhoto.s3Key = hashName
    		shipmentPhoto.photoDate = datetime.now()
    		try :
    			db.session.add(shipmentPhoto)
    			db.session.commit()
    			# Synch up the Shipment object.
    			shipment = shipment_for_id(shipment.id)
    			db.session.refresh(shipment)
    			status = ERR_NONE
    		except Exception as ex:
    			db.session.rollback()
    			print 'Unable to save ShipmentPhoto [%s]' % str(ex)
    		else:
    			# Something else has gone wrong.
    			print 'Error Saving Shipment ' + str(e)
    	else :
    		status = ERR_NO_SHIPMENT
    		error = "No shipment defined"
    except Exception as ex :
    	error = str(ex)
    	status = ERR_NO_SHIPMENT

    retVal['status'] = status
    retVal['error'] = error

    return retVal

if __name__ == "__main__":
    application.run(debug=True,host='0.0.0.0',port=8888)
    # application.run(debug=True,host='172.20.10.4',port=9999)

