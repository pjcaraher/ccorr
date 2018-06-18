from application import db
from application.models import User, Job, Shipment, ShipmentPhoto, ShipmentComment, Permission, Vendor, JobMap
db.create_all()

print("DB created.")

