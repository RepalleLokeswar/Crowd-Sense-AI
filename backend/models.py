from backend.extensions import db

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='user') # 'admin' or 'user'

class Zone(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    points_json = db.Column(db.Text, nullable=False) # Store valid JSON string of coords
    threshold = db.Column(db.Integer, default=10)

class Alert(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    zone_name = db.Column(db.String(50))
    message = db.Column(db.String(200))
    timestamp = db.Column(db.DateTime, default=db.func.now())
    is_read = db.Column(db.Boolean, default=False)

class SystemLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=db.func.now())
    event = db.Column(db.String(50)) # e.g. "Zone Created", "System Start"
    description = db.Column(db.String(200))
    user = db.Column(db.String(80)) # Username or 'System'

class AnalyticsData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=db.func.now())
    zone_name = db.Column(db.String(50))
    count = db.Column(db.Integer)
