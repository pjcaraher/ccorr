from application import db
# from application.models import User, Job, Shipment, ShipmentPhoto, Permission, Vendor
from application.models import User, Shipment, ShipmentPhoto
db.create_all()

print("DB created.")

