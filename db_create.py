from application import db
from application.models import User, Job, Shipment, ShipmentPhoto, Permission

db.create_all()

print("DB created.")

