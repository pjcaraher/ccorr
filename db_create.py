from application import db
# from application.models import User, Job, Shipment, ShipmentPhoto, ShipmentComment, Permission, Vendor, JobMap
from application.models import JobMap
db.create_all()

print("DB created.")

