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

class User(db.Model):
	__tablename__ = 'User'
	id = db.Column(db.Integer, primary_key=True)
	email = db.Column(db.String(32), unique=True)
	firstName = db.Column(db.String(32))
	lastName = db.Column(db.String(32))
	hashPassword = db.Column(db.String(64))
	passwordRequiresReset = db.Column(db.Boolean)
	permissionId = db.Column(db.Integer, db.ForeignKey('Permission.id'))
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
	
		print "PJC user is " + str(returnDict)
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
		return "%s:%s" % (salt, hash)

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

class Job(db.Model):
	__tablename__ = 'Job'
	id = db.Column(db.Integer, primary_key=True)
	name = db.Column(db.String(64))
	shipments = db.relationship('Shipment', backref='job')

	def __repr__(self):
		return '<Job %r>' % self.name

	def vendors(self):
		userIds = []
		result = db.session.connection().execute("Select user_id from UserJob, User where User.id = UserJob.user_id and User.permissionId = 4 and UserJob.job_id = " + str(self.id))
		for row in result :
			userIds.append(row[0])
		vendors = db.session.query(User).filter(User.id.in_(userIds)).all()
		return vendors

	def asDict(self):
		returnDict = {}
		returnDict['id'] = str(self.id)
		returnDict['name'] = str(self.name)
	
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
	jobId = db.Column(db.Integer, db.ForeignKey('Job.id'))
	vendorId = db.Column(db.Integer, db.ForeignKey('User.id'))
	photos = db.relationship('ShipmentPhoto', backref='shipment')

	def __repr__(self):
		return '<Shipment %r>' % self.id

	def vendor(self):
		vendor = db.session.query(User).filter_by(id=self.vendorId).first()
		return vendor

	def __lt__(self, other):
		if self.expectedDate :
			if other.expectedDate :
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

