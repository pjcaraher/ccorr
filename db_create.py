from application import db
# from application.models import User, Job, Vendor, Shipment, ShipmentPhoto
from application.models import ShipmentPhoto

db.create_all()

print("DB created.")

