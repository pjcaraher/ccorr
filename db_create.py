from application import db
from application.models import User, Job, Shipment, ShipmentPhoto, Permission, VendorJobConfig
db.create_all()

print("DB created.")

