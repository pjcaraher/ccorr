from application import db
import json
import hashlib
import random
import string
import base64
from validate_email import validate_email

userJobs = db.Table('UserJob',
       	db.Column('user_id', db.Integer, db.ForeignKey('User.id')),
       	db.Column('job_id', db.Integer, db.ForeignKey('Job.id'))
)

vendorJobs = db.Table('VendorJob',
       	db.Column('vendor_id', db.Integer, db.ForeignKey('Vendor.id')),
       	db.Column('job_id', db.Integer, db.ForeignKey('Job.id'))
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
	shipments = db.relationship('Shipment', backref='user')
	jobs = db.relationship('Job' ,
                                  secondary=userJobs,
                                  backref=db.backref('users', lazy=True),
                                  lazy='subquery')

	def __repr__(self):
		return '<User %r %r>' % (self.firstName, self.lastName)

	def name(self):
		return self.firstName

	def asDict(self):
		returnDict = {}
		returnDict['id'] = str(self.id)
		returnDict['email'] = str(self.email)
		returnDict['firstName'] = str(self.firstName)
		returnDict['lastName'] = str(self.lastName)
		if self.permissionId :
			returnDict['permissionId'] = str(self.permissionId)
		returnDict['passwordRequiresReset'] = str(self.passwordRequiresReset)
	
		return returnDict

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
	address = db.Column(db.String(128))
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
		returnDict['showDeliveryNumber'] = self.showDeliveryNumber
		returnDict['showContactName'] = self.showContactName
		returnDict['showContactNumber'] = self.showContactNumber
		returnDict['showBOLNumber'] = self.showBOLNumber
		returnDict['showSpecialInstructions'] = self.showSpecialInstructions
		returnDict['showDescriptionOfGoods'] = self.showDescriptionOfGoods
		returnDict['showTruckingCompany'] = self.showTruckingCompany
		returnDict['showNumberOfPackages'] = self.showNumberOfPackages
		returnDict['showTypeOfTruck'] = self.showTypeOfTruck
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
	vendorNotes = db.Column(db.String(256))
	jobId = db.Column(db.Integer, db.ForeignKey('Job.id'))
	vendorId = db.Column(db.Integer, db.ForeignKey('User.id'))
	photos = db.relationship('ShipmentPhoto', backref='shipment')

	def __repr__(self):
		return '<Shipment %r>' % self.id

	def vendor(self):
		vendor = db.session.query(User).filter_by(id=self.vendorId).first()
		return vendor

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
		returnDict['expectedDate'] = str(self.expectedDate)
		returnDict['arrivalDate'] = str(self.arrivalDate)
		returnDict['shippedDate'] = str(self.shippedDate)
	
		return returnDict

	def json(self):
		returnDict = self.asDict()
		return json.dumps(returnDict)

class ShipmentPhoto(db.Model):
	__tablename__ = 'ShipmentPhoto'
	id = db.Column(db.Integer, primary_key=True)
	shipmentId = db.Column(db.Integer, db.ForeignKey('Shipment.id'))
	photoDate = db.Column(db.DateTime)
	image = db.Column(db.LargeBinary)

	def __repr__(self):
		return '<ShipmentPhoto %r>' % self.id

	def src(self):
		return '/static/images/shipmentPhoto.' + str(self.id) + '.jpg'

	def asDict(self):
		returnDict = {}
		returnDict['id'] = str(self.id)
		returnDict['photoDate'] = str(self.photoDate)
		# print 'PJC base64 encoding image'
		returnDict['image'] = base64.b64encode(self.image)
	
		return returnDict

	def json(self):
		returnDict = self.asDict()
		return json.dumps(returnDict)

