# edit the URI below to add your RDS password and your AWS URL
# The other elements are the same as used in the tutorial
# format: (user):(password)@(db_identifier).amazonaws.com:3306/(db_name)

# SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:ccorr0828@ccorr-staging.cqe1n95npqmz.us-west-2.rds.amazonaws.com:3306/ccorr'
SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:root@localhost:3306/ccorr'

# Uncomment the line below if you want to work with a local DB
#SQLALCHEMY_DATABASE_URI = 'sqlite:///test.db'

SQLALCHEMY_POOL_SIZE = 100
SQLALCHEMY_POOL_RECYCLE = 280

WTF_CSRF_ENABLED = True
SECRET_KEY = 'dsaf0897sfdg45sfdgfdsaqzdf98sdf0a'


