import unittest
from flask import url_for
from flask_mail import Message
from app import create_app, db, mail
from app.models.job import Job, Status
from app.services.token_service import TokenService
from config import TestingConfig
import os
import shutil
from pathlib import Path
import re
from io import BytesIO

class TestJobFlows(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestingConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.create_all()
        
        # Store sent emails
        self.sent_emails = []
        def record_messages(message):
            self.sent_emails.append(message)
        mail.send = record_messages
        
        # Set up test directories
        self.test_jobs_root = Path(self.app.config['JOBS_ROOT'])
        for folder in self.app.config['STATUS_FOLDERS']:
            os.makedirs(self.test_jobs_root / folder, exist_ok=True)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        # Clean up test directories
        if self.test_jobs_root.exists():
            shutil.rmtree(self.test_jobs_root)
        self.app_context.pop()
        self.sent_emails = []

    def login_staff(self):
        """Helper method to login as staff"""
        return self.client.post('/staff/login', data={
            'password': self.app.config['STAFF_PASSWORD']
        }, follow_redirects=True)

    def create_test_file(self, job):
        """Helper to create a test file for a job."""
        source_path = self.test_jobs_root / job.status / job.filename
        source_path.parent.mkdir(parents=True, exist_ok=True)
        source_path.write_text("Test file content")
        return source_path

    def test_complete_job_flow(self):
        """Test the complete job flow from submission to confirmation."""
        # 1. Submit job
        with open(os.path.join(os.path.dirname(__file__), 'test_files/test.stl'), 'rb') as f:
            response = self.client.post('/submit', data={
                'student_name': 'John Smith',
                'student_email': 'john@example.com',
                'file': (f, 'test.stl'),
                'printer': 'Prusa MK4S',
                'color': 'Blue',
                'material': 'PLA'
            }, follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Submission Confirmed', response.data)
        
        # Get the created job
        job = Job.query.filter_by(student_email='john@example.com').first()
        self.assertIsNotNone(job)
        self.assertEqual(job.status, Status.UPLOADED.value)
        
        # Create test file
        self.create_test_file(job)
        
        # 2. Staff approves job
        self.login_staff()
        response = self.client.post(f'/job/{job.id}/approve', data={
            'weight_g': 100,
            'time_min': 120,
            'printer': 'Prusa MK4S',
            'color': 'Blue',
            'material': 'PLA'
        }, follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Job approved', response.data)
        
        # Verify job status and email
        job = Job.query.get(job.id)
        self.assertEqual(job.status, Status.PENDING.value)
        self.assertIsNotNone(job.confirm_url)
        self.assertEqual(len(self.sent_emails), 1)
        self.assertIn('john@example.com', self.sent_emails[0].recipients)
        
        # Extract confirmation token from email
        email_body = self.sent_emails[0].html
        token_match = re.search(r'/job/confirm/([^"]+)', email_body)
        self.assertIsNotNone(token_match)
        token = token_match.group(1)
        
        # 3. Student confirms job
        response = self.client.get(f'/job/confirm/{token}')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Confirm Your 3D Print Job', response.data)
        
        response = self.client.post(f'/job/confirm/{token}', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Your 3D print job has been confirmed', response.data)
        
        # Verify final job status
        job = Job.query.get(job.id)
        self.assertEqual(job.status, Status.READY_TO_PRINT.value)
        self.assertTrue(job.student_confirmed)
        self.assertIsNone(job.confirm_url)  # URL should be invalidated
        
        # Verify file location
        file_path = self.test_jobs_root / Status.READY_TO_PRINT.value / job.filename
        self.assertTrue(file_path.exists())

    def test_job_rejection_flow(self):
        """Test the job rejection flow."""
        # 1. Submit job
        with open(os.path.join(os.path.dirname(__file__), 'test_files/test.stl'), 'rb') as f:
            response = self.client.post('/submit', data={
                'student_name': 'John Smith',
                'student_email': 'john@example.com',
                'file': (f, 'test.stl'),
                'printer': 'Prusa MK4S',
                'color': 'Blue'
            }, follow_redirects=True)
        
        job = Job.query.filter_by(student_email='john@example.com').first()
        self.create_test_file(job)
        
        # 2. Staff rejects job
        self.login_staff()
        response = self.client.post(f'/job/{job.id}/reject', data={
            'reasons': ['Too large', 'Unsupported overhangs']
        }, follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'success', response.data)  # JSON response
        
        # Verify job status and email
        job = Job.query.get(job.id)
        self.assertEqual(job.status, Status.REJECTED.value)
        self.assertEqual(job.reject_reasons, ['Too large', 'Unsupported overhangs'])
        self.assertEqual(len(self.sent_emails), 1)
        self.assertIn('john@example.com', self.sent_emails[0].recipients)
        
        # Verify file location
        file_path = self.test_jobs_root / Status.REJECTED.value / job.filename
        self.assertTrue(file_path.exists())

    def test_expired_token_flow(self):
        """Test handling of expired confirmation tokens."""
        # Create and approve a job
        job = Job(
            student_name='John Smith',
            student_email='john@example.com',
            filename='test.stl',
            original_filename='test.stl',
            status=Status.PENDING,
            printer='Prusa MK4S',
            color='Blue',
            material='PLA',
            weight_g=100,
            time_min=120
        )
        db.session.add(job)
        db.session.commit()
        self.create_test_file(job)
        
        # Generate an expired token
        token = TokenService.generate_token(job)
        
        # Try to confirm with expired token
        response = self.client.get(
            f'/job/confirm/{token}',
            follow_redirects=True
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'confirmation link has expired', response.data)
        
        # Verify job status unchanged
        job = Job.query.get(job.id)
        self.assertEqual(job.status, Status.PENDING.value)
        self.assertFalse(job.student_confirmed)

if __name__ == '__main__':
    unittest.main() 