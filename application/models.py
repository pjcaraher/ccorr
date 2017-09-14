from application import db
import json
import hashlib
import random
import string
import base64
from validate_email import validate_email

class User(db.Model):
	__tablename__ = 'User'
	id = db.Column(db.Integer, primary_key=True)
	email = db.Column(db.String(32), unique=True)
	firstName = db.Column(db.String(32))
	lastName = db.Column(db.String(32))
	hashPassword = db.Column(db.String(64))
	passwordRequiresReset = db.Column(db.Boolean)

	def __repr__(self):
		return '<User %r %r>' % (self.firstName, self.lastName)

	def asDict(self):
		returnDict = {}
		returnDict['id'] = str(self.id)
		returnDict['email'] = str(self.email)
		returnDict['firstName'] = str(self.firstName)
		returnDict['lastName'] = str(self.lastName)
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


class Job(db.Model):
	__tablename__ = 'Job'
	id = db.Column(db.Integer, primary_key=True)
	name = db.Column(db.String(64))
	vendors = db.relationship('Vendor', backref='job')
	shipments = db.relationship('Shipment', backref='job')

	def __repr__(self):
		return '<Job %r>' % self.name

	def asDict(self):
		returnDict = {}
		returnDict['id'] = str(self.id)
		returnDict['name'] = str(self.name)
	
		return returnDict

	def json(self):
		returnDict = self.asDict()
		return json.dumps(returnDict)

class Vendor(db.Model):
	__tablename__ = 'Vendor'
	id = db.Column(db.Integer, primary_key=True)
	name = db.Column(db.String(64))
	jobId = db.Column(db.Integer, db.ForeignKey('Job.id'))
	shipments = db.relationship('Shipment', backref='vendor')

	def __repr__(self):
		return '<Vendor %r>' % self.name

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
	vendorId = db.Column(db.Integer, db.ForeignKey('Vendor.id'))
	photos = db.relationship('ShipmentPhoto', backref='shipment')

	def __repr__(self):
		return '<Shipment %r>' % self.id

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

