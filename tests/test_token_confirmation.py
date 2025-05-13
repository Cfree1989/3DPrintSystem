import unittest
import os
from app import create_app, db
from app.models.job import Job, Status
from app.services.token_service import TokenService
from config import TestingConfig
from pathlib import Path

class TestTokenConfirmation(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestingConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.create_all()
        
        # Create test directories
        self.test_jobs_root = Path(self.app.config['JOBS_ROOT'])
        for status in [s.value for s in Status]:
            os.makedirs(self.test_jobs_root / status, exist_ok=True)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        # Clean up test directories
        import shutil
        shutil.rmtree(self.test_jobs_root, ignore_errors=True)
        self.app_context.pop()

    def create_test_file(self, job):
        """Helper to create a test file for a job"""
        file_path = job.get_file_path()
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, 'w') as f:
            f.write('test content')

    def test_token_generation(self):
        """Test token generation for a job"""
        job = Job(
            student_name='John Smith',
            student_email='john@example.com',
            filename='test.stl',
            original_filename='test.stl',
            status=Status.PENDING,
            printer='Prusa MK4S',
            color='Blue',
            weight_g=100,
            time_min=120
        )
        db.session.add(job)
        db.session.commit()

        token = TokenService.generate_token(job)
        self.assertIsNotNone(token)
        
        # Verify token
        job_id, error = TokenService.verify_token(token)
        self.assertIsNone(error)
        self.assertEqual(job_id, job.id)

    def test_valid_token_confirmation(self):
        """Test successful job confirmation with valid token"""
        job = Job(
            student_name='John Smith',
            student_email='john@example.com',
            filename='test.stl',
            original_filename='test.stl',
            status=Status.PENDING,
            printer='Prusa MK4S',
            color='Blue',
            weight_g=100,
            time_min=120
        )
        db.session.add(job)
        db.session.commit()

        # Create test file
        self.create_test_file(job)

        # Generate confirmation token
        token = TokenService.generate_token(job)

        # Try to confirm the job
        response = self.client.get(f'/job/confirm/{token}')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Please confirm your print job details', response.data)

        # Submit confirmation
        response = self.client.post(f'/job/confirm/{token}', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Job confirmed successfully', response.data)

        # Check job status
        job = Job.query.get(job.id)
        self.assertEqual(job.status, Status.READY_TO_PRINT.value)

    def test_expired_token(self):
        """Test handling of expired tokens"""
        job = Job(
            student_name='John Smith',
            student_email='john@example.com',
            filename='test.stl',
            original_filename='test.stl',
            status=Status.PENDING,
            printer='Prusa MK4S',
            color='Blue',
            weight_g=100,
            time_min=120
        )
        db.session.add(job)
        db.session.commit()

        # Generate an expired token
        token = TokenService.generate_token(job)
        
        # Try to confirm with expired token (using 0 seconds expiry)
        job_id, error = TokenService.verify_token(token, expiration=0)
        self.assertIsNone(job_id)
        self.assertIn('expired', error)

        # Try to use expired token in route
        response = self.client.get(f'/job/confirm/{token}', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'confirmation link has expired', response.data)

    def test_wrong_status_confirmation(self):
        """Test confirming a job that's not in PENDING status"""
        job = Job(
            student_name='John Smith',
            student_email='john@example.com',
            filename='test.stl',
            original_filename='test.stl',
            status=Status.UPLOADED,  # Should be PENDING for confirmation
            printer='Prusa MK4S',
            color='Blue',
            weight_g=100,
            time_min=120
        )
        db.session.add(job)
        db.session.commit()

        # Generate confirmation token
        token = TokenService.generate_token(job)

        # Try to confirm
        response = self.client.get(f'/job/confirm/{token}', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'must be in \'Pending\' status', response.data) 