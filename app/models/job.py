from enum import Enum
from datetime import datetime
from extensions import db

class Status(str, Enum):
    UPLOADED = 'Uploaded'
    PENDING = 'Pending'
    REJECTED = 'Rejected'
    READY_TO_PRINT = 'ReadyToPrint'
    PRINTING = 'Printing'
    COMPLETED = 'Completed'
    PAID_PICKED_UP = 'PaidPickedUp'

class Job(db.Model):
    __tablename__ = 'jobs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(20), nullable=False, default=Status.UPLOADED)
    printer = db.Column(db.String(50))
    color = db.Column(db.String(50))
    material = db.Column(db.String(50))
    weight_g = db.Column(db.Float)
    time_min = db.Column(db.Integer)
    cost = db.Column(db.Float)
    notes = db.Column(db.Text)
    student_confirmed = db.Column(db.Boolean, default=False)
    rejection_reasons = db.Column(db.JSON)  # list of reasons
    thumbnail_path = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __init__(self, user_id, filename, original_filename, printer=None, color=None, material=None):
        self.user_id = user_id
        self.filename = filename
        self.original_filename = original_filename
        self.printer = printer
        self.color = color
        self.material = material
    
    def update_status(self, new_status: Status):
        """Update the job status and handle any necessary side effects"""
        if not isinstance(new_status, Status):
            raise ValueError(f"Invalid status: {new_status}")
        
        old_status = self.status
        self.status = new_status
        
        # Add status change to notes
        status_note = f"Status changed from {old_status} to {new_status}"
        if self.notes:
            self.notes = f"{self.notes}\n{status_note}"
        else:
            self.notes = status_note
        
        self.updated_at = datetime.utcnow()
    
    def calculate_cost(self):
        """Calculate the cost of the print job based on material weight and time"""
        if not self.weight_g or not self.time_min:
            return
        
        # Base cost calculation
        material_cost = self.weight_g * 0.05  # $0.05 per gram
        time_cost = (self.time_min / 60) * 2  # $2 per hour
        
        # Add markup for different printers
        printer_markup = {
            'Prusa MK4S': 1.0,  # Standard markup
            'Prusa XL': 1.2,    # 20% markup for large format
            'Raise3D': 1.3,     # 30% markup for high resolution
            'Formlabs': 1.5     # 50% markup for resin
        }
        
        markup = printer_markup.get(self.printer, 1.0)
        self.cost = round((material_cost + time_cost) * markup, 2)
    
    def get_time_display(self):
        """Get a human-readable time display"""
        if not self.time_min:
            return "Not set"
        hours = self.time_min // 60
        minutes = self.time_min % 60
        return f"{hours}h {minutes}m"
    
    def __repr__(self):
        return f'<Job {self.id} {self.original_filename}>' 