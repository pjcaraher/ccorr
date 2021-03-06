from application import db
import json
import config
import os
import hashlib
import random
import string
import base64
import boto3
import botocore
from validate_email import validate_email

userJobs = db.Table('UserJob',
       	db.Column('user_id', db.Integer, db.ForeignKey('User.id')),
       	db.Column('job_id', db.Integer, db.ForeignKey('Job.id'))
)

vendorJobs = db.Table('VendorJob',
       	db.Column('vendor_id', db.Integer, db.ForeignKey('Vendor.id')),
       	db.Column('job_id', db.Integer, db.ForeignKey('Job.id'))
)

shipmentMaps = db.Table('ShipmentMap',
       	db.Column('shipment_id', db.Integer, db.ForeignKey('Shipment.id')),
       	db.Column('jobmap_id', db.Integer, db.ForeignKey('JobMap.id'))
)

class User(db.Model):
	__tablename__ = 'User'
	id = db.Column(db.Integer, primary_key=True)
	email = db.Column(db.String(32), unique=True)
	firstName = db.Column(db.String(32))
	lastName = db.Column(db.String(32))
	hashPassword = db.Column(db.String(64))
	passwordRequiresReset = db.Column(db.Boolean)
	permissionId = db.Column(db.Integer, db.ForeignKey('Permission.id'))
	vendorId = db.Column(db.Integer, db.ForeignKey('Vendor.id'))
	jobs = db.relationship('Job' ,
                                  secondary=userJobs,
                                  backref=db.backref('users', lazy=True),
                                  lazy='subquery')

	def __repr__(self):
		return '<User %r %r>' % (self.firstName, self.lastName)

	def name(self):
		return self.firstName + " " + self.lastName

	def asDict(self):
		returnDict = {}
		returnDict['id'] = str(self.id)
		returnDict['email'] = str(self.email)
		returnDict['firstName'] = str(self.firstName)
		returnDict['lastName'] = str(self.lastName)
		if self.permissionId :
			returnDict['permissionId'] = str(self.permissionId)

		jobIds = []
		for job in self.jobs:
			jobIds.append(job.id)
		returnDict['jobIds'] = ','.join(str(e) for e in jobIds)
		returnDict['passwordRequiresReset'] = str(self.passwordRequiresReset)
		returnDict['permissionName'] = self.permissionName()
	
		return returnDict

	def asStringDict(self):
		returnDict = self.asDict()

		for k, v in returnDict.items():
			returnDict[k] = str(v)
	
		return returnDict

	def hasPermissionToSeeAllComments(self):
		return self.permissionId < 4

	def json(self):
		returnDict = self.asDict()
		return json.dumps(returnDict)

	def setEmail(self,e):
		self.email = e.lower()

	def setPassword(self, password) :
		hash = self.hashP(password)
		self.hashPassword = hash

	def passwordsMatch(self, password) :
		hash = self.hashP(password)
		return self.hashPassword == hash

	def hasPermission(self, permission) :
		torf = False
		if self.permissionId :
			if self.permissionId <= permission :
				torf = True
		return torf

	def permissionName(self) :
		permissionName = "Unkown"
		if self.permissionId == config.PERMISSION_ADMIN :
			permissionName = "Admin"
		elif self.permissionId == config.PERMISSION_PM :
			permissionName = "Project Manager"
		elif self.permissionId == config.PERMISSION_FS :
			permissionName = "Field Staff"
		elif self.permissionId == config.PERMISSION_VENDOR :
			permissionName = "Vendor"

		return permissionName

	def hasJob(self, job) :
		torf = False
		if 1 >= self.permissionId :
			torf = True
		else :
			for _job in self.jobs :
				if _job.id == job.id :
					torf = True
					break
		return torf

	@staticmethod
	def tmpPassword() :
		tmpPass = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(6))
		return tmpPass

	@staticmethod
	def isValidEmail(email) :
		return validate_email(email)

	@staticmethod
	def hashP(password) :
		salt = "JJwV/8"

		hash = hashlib.md5(salt + password).hexdigest()
		return "%s" % (hash)

class Permission(db.Model):
	__tablename__ = 'Permission'
	id = db.Column(db.Integer, primary_key=True)
	name = db.Column(db.String(32))
	description = db.Column(db.String(128))

	def __repr__(self):
		return '<Permission %r>' % self.name

	def asDict(self):
		returnDict = {}
		returnDict['id'] = str(self.id)
		returnDict['name'] = str(self.name)
		returnDict['description'] = str(self.description)
	
		return returnDict

class Vendor(db.Model):
	__tablename__ = 'Vendor'
	id = db.Column(db.Integer, primary_key=True)
	name = db.Column(db.String(32))
	contact = db.Column(db.String(32))
	phone = db.Column(db.String(32))
	emailList = db.Column(db.String(256))
	shipments = db.relationship('Shipment', backref='vendor')
	jobs = db.relationship('Job' ,
                                  secondary=vendorJobs,
                                  backref=db.backref('vendors', lazy=True),
                                  lazy='subquery')

	def __repr__(self):
		return '<Vendor %r>' % self.name

	def users(self):
		users = []
		query = db.session.query(User).filter_by(vendorId=self.id)
		for user in query :
			users.append(user)
		return users

	def asDict(self):
		returnDict = {}
		returnDict['id'] = str(self.id)
		returnDict['name'] = str(self.name)
		returnDict['contact'] = str(self.contact)
		returnDict['phone'] = str(self.phone)
		returnDict['emailList'] = str(self.emailList)

		jobIds = []
		for job in self.jobs:
			jobIds.append(job.id)
		returnDict['jobIds'] = ','.join(str(e) for e in jobIds)

		users = []
		for user in self.users():
			users.append(user.asDict())
		returnDict['users'] = str(users)
	
		print "PJC Vendor asDict is : " + str(returnDict)
		return returnDict

	def belongsToJob(self, job):
		belongsToJob = False

		for _job in self.jobs:
			if _job.id == job.id :
				belongsToJob = True
				break

		return belongsToJob

class Job(db.Model):
	__tablename__ = 'Job'
	id = db.Column(db.Integer, primary_key=True)
	name = db.Column(db.String(64))
	number = db.Column(db.String(64))
	street = db.Column(db.String(128))
	city = db.Column(db.String(64))
	state = db.Column(db.String(5))
	zip = db.Column(db.String(10))
	instructions = db.Column(db.String(1024))
	showDeliveryNumber = db.Column(db.Boolean)
	showContactName = db.Column(db.Boolean)
	showContactNumber = db.Column(db.Boolean)
	showBOLNumber = db.Column(db.Boolean)
	showSpecialInstructions = db.Column(db.Boolean)
	showDescriptionOfGoods = db.Column(db.Boolean)
	showTruckingCompany = db.Column(db.Boolean)
	showNumberOfPackages = db.Column(db.Boolean)
	showTypeOfTruck = db.Column(db.Boolean)
	showDriverName = db.Column(db.Boolean)
	showDriverPhone = db.Column(db.Boolean)
	showTrackingNumber = db.Column(db.Boolean)
	showWeightOfLoad = db.Column(db.Boolean)
	showVendorNotes = db.Column(db.Boolean)
	showDeliveryDate = db.Column(db.Boolean)
	showDateLoaded = db.Column(db.Boolean)
	attachBOL = db.Column(db.Boolean)
	attachPackingList = db.Column(db.Boolean)
	attachPhotos = db.Column(db.Boolean)
	attachMap = db.Column(db.Boolean)
	shipments = db.relationship('Shipment', backref='job')
	maps = db.relationship('JobMap', backref='job')

	def __repr__(self):
		return '<Job %r>' % self.name

	def vendorList(self):
		# userIds = []
		# vendors = []
		# result = db.session.connection().execute("Select user_id from UserJob, User where User.id = UserJob.user_id and User.permissionId = 4 and UserJob.job_id = " + str(self.id))
		# for row in result :
			# userIds.append(row[0])
		# if len(userIds) > 0 :
			# result2 = db.session.query(User).filter(User.id.in_(userIds)).all()
			# for row in result2 :
				# vendors.append(row)
		vendorList = []
		for vendor in self.vendors :
			vendorList.append(vendor)
		return vendorList

	def asDict(self):
		returnDict = {}
		returnDict['id'] = str(self.id)
		returnDict['name'] = str(self.name)
		returnDict['number'] = str(self.number)
		returnDict['street'] = str(self.street)
		returnDict['city'] = str(self.city)
		returnDict['state'] = str(self.state)
		returnDict['zip'] = str(self.zip)
		returnDict['instructions'] = str(self.instructions)
		returnDict['showDeliveryNumber'] = self.showDeliveryNumber
		returnDict['showContactName'] = self.showContactName
		returnDict['showContactNumber'] = self.showContactNumber
		returnDict['showBOLNumber'] = self.showBOLNumber
		returnDict['showSpecialInstructions'] = self.showSpecialInstructions
		returnDict['showDescriptionOfGoods'] = self.showDescriptionOfGoods
		returnDict['showTruckingCompany'] = self.showTruckingCompany
		returnDict['showNumberOfPackages'] = self.showNumberOfPackages
		returnDict['showTypeOfTruck'] = self.showTypeOfTruck
		returnDict['showDriverName'] = self.showDriverName
		returnDict['showDriverPhone'] = self.showDriverPhone
		returnDict['showTrackingNumber'] = self.showTrackingNumber
		returnDict['showWeightOfLoad'] = self.showWeightOfLoad
		returnDict['showVendorNotes'] = self.showVendorNotes
		returnDict['showDeliveryDate'] = self.showDeliveryDate
		returnDict['showDateLoaded'] = self.showDateLoaded
		returnDict['attachBOL'] = self.attachBOL
		returnDict['attachPackingList'] = self.attachPackingList
		returnDict['attachPhotos'] = self.attachPhotos
		returnDict['attachMap'] = self.attachMap
	
		return returnDict

	def asStringDict(self):
		returnDict = self.asDict()

		for k, v in returnDict.items():
			returnDict[k] = str(v)
	
		return returnDict

	def json(self):
		returnDict = self.asDict()
		return json.dumps(returnDict)

class Shipment(db.Model):
	__tablename__ = 'Shipment'
	id = db.Column(db.Integer, primary_key=True)
	shippedDate = db.Column(db.DateTime)
	expectedDate = db.Column(db.DateTime)
	arrivalDate = db.Column(db.DateTime)
	description = db.Column(db.String(512))
	truckingCompany = db.Column(db.String(128))
	truckType = db.Column(db.String(128))
	weight = db.Column(db.String(64))
	numberOfPackages = db.Column(db.Integer)
	deliveryNumber = db.Column(db.String(64))
	bolNumber = db.Column(db.String(64))
	specialInstructions = db.Column(db.String(256))
	trackingNumber = db.Column(db.String(64))
	vendorNotes = db.Column(db.String(1024))
	jobId = db.Column(db.Integer, db.ForeignKey('Job.id'))
	vendorId = db.Column(db.Integer, db.ForeignKey('Vendor.id'))
	driverName = db.Column(db.String(64))
	driverPhone = db.Column(db.String(64))
	photos = db.relationship('ShipmentPhoto', backref='shipment')
	comments = db.relationship('ShipmentComment', backref='shipment')
	maps = db.relationship('JobMap' ,
                                  secondary=shipmentMaps,
                                  backref=db.backref('shipments', lazy=True),
                                  lazy='subquery')

	def __repr__(self):
		return '<Shipment %r>' % self.id

	def vendor(self):
		vendor = db.session.query(User).filter_by(id=self.vendorId).first()
		return vendor

	def hasMap(self, map):
		hasMap = False
		for _map in self.maps :
			if _map.id == map.id :
				hasMap = True
				break
		return hasMap

	def reversedComments(self):
		return list(reversed(self.comments))

	# First return the arrived Shipments, the most recent at top.
	# Second, return the expected Shipments, the most recent at top.
	def __lt__(self, other):
		if self.arrivalDate :
			if other.arrivalDate :
				return self.arrivalDate < other.arrivalDate
			else :
				return True
		elif self.expectedDate :
			if other.arrivalDate :
				return False
			elif other.expectedDate :
				return self.expectedDate < other.expectedDate
			else :
				return True
		else :
			return False


	def asDict(self):
		returnDict = {}
		returnDict['id'] = str(self.id)
		returnDict['description'] = str(self.description)
		if self.expectedDate :
			returnDict['expectedDate'] = str(self.expectedDate)
		if self.arrivalDate :
			returnDict['arrivalDate'] = str(self.arrivalDate)
		if self.shippedDate :
			returnDict['shippedDate'] = str(self.shippedDate)
		if self.truckingCompany :
			returnDict['truckingCompany'] = str(self.truckingCompany)
		if self.truckType :
			returnDict['truckType'] = str(self.truckType)
		if self.weight :
			returnDict['weight'] = str(self.weight)
		if self.numberOfPackages :
			returnDict['numberOfPackages'] = str(self.numberOfPackages)
		if self.deliveryNumber :
			returnDict['deliveryNumber'] = str(self.deliveryNumber)
		if self.bolNumber :
			returnDict['bolNumber'] = str(self.bolNumber)
		if self.specialInstructions :
			returnDict['specialInstructions'] = str(self.specialInstructions)
		if self.trackingNumber :
			returnDict['trackingNumber'] = str(self.trackingNumber)
		if self.vendorNotes :
			returnDict['vendorNotes'] = str(self.vendorNotes)
		if self.driverName :
			returnDict['driverName'] = str(self.driverName)
		if self.driverPhone :
			returnDict['driverPhone'] = str(self.driverPhone)
		returnDict['jobId'] = str(self.jobId)
		returnDict['vendorId'] = str(self.vendorId)

		return returnDict

	def asStringDict(self):
		returnDict = self.asDict()
		reversedComments = self.reversedComments()
		commentArray = []
		photoArray = []

		for k, v in returnDict.items():
			returnDict[k] = str(v)

		for comment in reversedComments :
			commentArray.append(comment.asStringDict())

		returnDict['reversedComments'] = commentArray
	
		for photo in self.photos :
			photoArray.append(photo.asStringDict())

		returnDict['photos'] = photoArray
	
		return returnDict

	def json(self):
		returnDict = self.asDict()
		return json.dumps(returnDict)

class ShipmentPhoto(db.Model):
	__tablename__ = 'ShipmentPhoto'
	id = db.Column(db.Integer, primary_key=True)
	shipmentId = db.Column(db.Integer, db.ForeignKey('Shipment.id'))
	photoDate = db.Column(db.DateTime)
	s3Key = db.Column(db.String(64))

	def __repr__(self):
		return '<ShipmentPhoto %r>' % self.id

	def image_url(self):
		url = os.environ['CLOUDFRONTURL'] + "/" + self.s3Key

		return url

	def asDict(self):
		returnDict = {}
		returnDict['id'] = str(self.id)
		returnDict['photoDate'] = str(self.photoDate)
		# print 'PJC base64 encoding image'
		returnDict['s3Key'] = self.s3Key
		returnDict['image_url'] = self.image_url()
	
		return returnDict

	def asStringDict(self):
		returnDict = self.asDict()

		for k, v in returnDict.items():
			returnDict[k] = str(v)

		returnDict['photoDate'] = self.photoDate.strftime("%-m/%d %-I:%M %p")
	
		return returnDict

	def json(self):
		returnDict = self.asDict()
		return json.dumps(returnDict)

class ShipmentComment(db.Model):
	__tablename__ = 'ShipmentComment'
	id = db.Column(db.Integer, primary_key=True)
	shipmentId = db.Column(db.Integer, db.ForeignKey('Shipment.id'))
	commentDate = db.Column(db.DateTime)
	comment = db.Column(db.String(1024))
	userId = db.Column(db.Integer, db.ForeignKey('User.id'))

	def __repr__(self):
		return '<ShipmentComment %r>' % self.id

	def user(self):
		user = db.session.query(User).filter_by(id=self.userId).first()
		return user

	def asDict(self):
		returnDict = {}
		returnDict['id'] = str(self.id)
		returnDict['comment'] = str(self.comment)
		returnDict['commentDate'] = str(self.commentDate)
	
		return returnDict

	def asStringDict(self):
		returnDict = self.asDict()

		for k, v in returnDict.items():
			returnDict[k] = str(v)

		returnDict['userName'] = str(self.user().name())
	
		return returnDict

	def json(self):
		returnDict = self.asDict()
		return json.dumps(returnDict)

class JobMap(db.Model):
	__tablename__ = 'JobMap'
	id = db.Column(db.Integer, primary_key=True)
	jobId = db.Column(db.Integer, db.ForeignKey('Job.id'))
	s3Key = db.Column(db.String(64))
	name = db.Column(db.String(256))
	type = db.Column(db.String(16))
	deleted = db.Column(db.Boolean)

	def __repr__(self):
		return '<JobMap %r>' % self.id

	def job(self):
		job = db.session.query(Job).filter_by(id=self.jobId).first()
		return job

	def image_url(self):
		url = os.environ['CLOUDFRONTURL'] + "/" + self.s3Key

		return url

	def asDict(self):
		returnDict = {}
		returnDict['id'] = str(self.id)
		returnDict['jobId'] = str(self.jobId)
		returnDict['s3Key'] = str(self.s3Key)
		returnDict['name'] = str(self.name)
		returnDict['type'] = str(self.type)
	
		return returnDict

	def json(self):
		returnDict = self.asDict()
		return json.dumps(returnDict)
