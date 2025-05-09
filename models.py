from extensions import db

class Job(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String, nullable=False)
    name = db.Column(db.String, nullable=False)
    email = db.Column(db.String, nullable=False)
    status = db.Column(db.String, nullable=False, default='Uploaded')
    weight = db.Column(db.Float, nullable=True)
    time_hours = db.Column(db.Integer, nullable=True)
    time_minutes = db.Column(db.Integer, nullable=True)
    printer = db.Column(db.String, nullable=True)
    color = db.Column(db.String, nullable=True)
    material = db.Column(db.String, nullable=True)
    cost = db.Column(db.Float, nullable=True)
    student_confirmed = db.Column(db.Boolean, default=False, nullable=False)
    rejection_reasons = db.Column(db.String, nullable=True)
    thumbnail_path = db.Column(db.String, nullable=True) 