import os
# edit the URI below to add your RDS password and your AWS URL
# The other elements are the same as used in the tutorial
# format: (user):(password)@(db_identifier).amazonaws.com:3306/(db_name)

SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://' + os.environ['DBUSER'] + ':' + os.environ['DBPASS'] + '@' + os.environ['DBNAME'] + '/ccorr'

SQLALCHEMY_POOL_SIZE = 100
SQLALCHEMY_POOL_RECYCLE = 280

WTF_CSRF_ENABLED = True
SECRET_KEY = 'dsaf0897sfdg45sfdgfdsaqzdf98sdf0a'

PERMISSION_ADMIN = 1
PERMISSION_PM = 2
PERMISSION_FS = 3
PERMISSION_VENDOR = 4


