from enum import Enum
from datetime import datetime
from extensions import db
from flask import current_app, url_for
from app.services.token_service import TokenService
import os
from pathlib import Path
from sqlalchemy import event
import json

class Status(str, Enum):
    """Job status enum."""
    UPLOADED = 'Uploaded'
    PENDING = 'Pending'
    CONFIRMED = 'Confirmed'
    PRINTING = 'Printing'
    COMPLETED = 'Completed'
    REJECTED = 'Rejected'
    FAILED = 'Failed'

class Job(db.Model):
    __tablename__ = 'jobs'
    
    id = db.Column(db.Integer, primary_key=True)
    student_name = db.Column(db.String(100), nullable=False)
    student_email = db.Column(db.String(120), nullable=False)
    filename = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    status = db.Column(db.String(50), nullable=False, default=Status.UPLOADED.value)
    printer = db.Column(db.String(50), nullable=False)
    color = db.Column(db.String(50))
    material = db.Column(db.String(50))
    weight_g = db.Column(db.Float)
    time_min = db.Column(db.Integer)
    cost = db.Column(db.Float)
    notes = db.Column(db.Text)
    student_confirmed = db.Column(db.Boolean, default=False)
    _reject_reasons = db.Column('reject_reasons', db.Text, default='[]')
    thumbnail_path = db.Column(db.String(255))
    confirm_url = db.Column(db.String(512))
    created_at = db.Column(db.DateTime, nullable=False)
    updated_at = db.Column(db.DateTime, nullable=False)
    
    def __init__(self, **kwargs):
        super(Job, self).__init__(**kwargs)
        self.created_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    @property
    def reject_reasons(self):
        """Get the list of rejection reasons."""
        return json.loads(self._reject_reasons)
    
    @reject_reasons.setter
    def reject_reasons(self, value):
        """Set the list of rejection reasons."""
        self._reject_reasons = json.dumps(value)
    
    def update_status(self, new_status):
        """Update the job status and timestamp."""
        if not isinstance(new_status, Status):
            raise ValueError(f"Invalid status: {new_status}")
        self.status = new_status.value
        self.updated_at = datetime.utcnow()
    
    def calculate_cost(self):
        """Calculate the total cost of the print job.
        
        The cost is calculated based on:
        - Material cost per gram
        - Time cost per hour
        - Base fee
        """
        if not self.weight_g or not self.time_min:
            raise ValueError("Weight and time must be set before calculating cost")
            
        # Get cost parameters from config
        material_cost_per_g = current_app.config.get('MATERIAL_COST_PER_G', 0.05)
        time_cost_per_hour = current_app.config.get('TIME_COST_PER_HOUR', 1.00)
        base_fee = current_app.config.get('BASE_FEE', 2.00)
        
        # Calculate material cost
        material_cost = self.weight_g * material_cost_per_g
        
        # Calculate time cost (convert minutes to hours)
        time_cost = (self.time_min / 60) * time_cost_per_hour
        
        # Calculate total cost
        self.cost = material_cost + time_cost + base_fee
        return self.cost
    
    def get_time_display(self):
        """Get a human-readable display of the print time."""
        if not self.time_min:
            return "Unknown"
        hours = self.time_min // 60
        minutes = self.time_min % 60
        return f"{hours}h {minutes}m"
    
    def generate_confirmation_token(self):
        """Generate a confirmation token and URL for the job."""
        token = TokenService.generate_token(self)
        self.confirm_url = url_for('main.confirm_job_by_token', token=token, _external=True)
        return self.confirm_url
    
    def __repr__(self):
        return f'<Job {self.id} {self.original_filename}>'

    def get_file_path(self):
        """Get the current path of the job's file."""
        jobs_root = Path(current_app.config['JOBS_ROOT'])
        return jobs_root / self.status / self.filename

    def cleanup_files(self):
        """Remove all files associated with this job."""
        try:
            # Remove the main file
            file_path = self.get_file_path()
            if file_path.exists():
                file_path.unlink()

            # Remove thumbnail if it exists
            thumbnail_path = Path(current_app.config['THUMBNAILS_DIR']) / f"{self.id}.png"
            if thumbnail_path.exists():
                thumbnail_path.unlink()

            return True
        except Exception as e:
            current_app.logger.error(f"Error cleaning up files for job {self.id}: {str(e)}")
            return False

@event.listens_for(Job, 'before_delete')
def cleanup_job_files(mapper, connection, target):
    """Event listener to clean up files when a job is deleted."""
    target.cleanup_files() 