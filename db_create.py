from application import db
from application.models import User, Job, Shipment, ShipmentPhoto, ShipmentComment, Permission, Vendor, Map, JobMap
# from application.models import ShipmentComment
db.create_all()

print("DB created.")

