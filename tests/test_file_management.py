import unittest
import os
import io
from pathlib import Path
from app import create_app, db
from app.models.job import Job, Status
from app.services.file_service import FileService, atomic_move
from config import TestingConfig
from werkzeug.datastructures import FileStorage

class TestFileManagement(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestingConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.create_all()
        
        # Set up test directories
        self.test_jobs_root = Path(self.app.config['JOBS_ROOT'])
        for folder in self.app.config['STATUS_FOLDERS']:
            os.makedirs(self.test_jobs_root / folder, exist_ok=True)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        # Clean up test directories
        if self.test_jobs_root.exists():
            import shutil
            shutil.rmtree(self.test_jobs_root)
        self.app_context.pop()

    def login_staff(self):
        """Helper method to login as staff"""
        return self.client.post('/staff/login', data={
            'password': self.app.config['STAFF_PASSWORD']
        }, follow_redirects=True)

    def create_test_file(self, filename, content=b'test content'):
        """Helper to create a test file."""
        return FileStorage(
            stream=io.BytesIO(content),
            filename=filename,
            content_type='application/octet-stream'
        )

    def test_secure_job_filename(self):
        """Test the secure job filename format"""
        # Test basic case
        filename = FileService.secure_job_filename(
            username="John Doe",
            printer="Prusa MK4S",
            color="Blue",
            original_filename="test.stl"
        )
        self.assertEqual(filename, "JohnDoe_PrusaMK4S_Blue_1.stl")
        
        # Test with special characters
        filename = FileService.secure_job_filename(
            username="Mary-Jane O'Connor",
            printer="Prusa XL",
            color="Dark Blue",
            original_filename="my model.stl"
        )
        self.assertEqual(filename, "MaryJaneOConnor_PrusaXL_DarkBlue_1.stl")
        
        # Test with multiple jobs (should increment ID)
        job1 = Job(
            student_name="Test User",
            student_email="test@example.com",
            filename="TestUser_PrusaMK4S_Blue_1.stl",
            original_filename="test1.stl",
            status=Status.UPLOADED,
            printer="Prusa MK4S",
            color="Blue"
        )
        db.session.add(job1)
        db.session.commit()
        
        filename = FileService.secure_job_filename(
            username="Another User",
            printer="Prusa MK4S",
            color="Red",
            original_filename="test2.stl"
        )
        self.assertEqual(filename, "AnotherUser_PrusaMK4S_Red_2.stl")

    def test_file_upload_and_movement(self):
        """Test file upload and movement through different status folders"""
        # Create and upload file
        file = self.create_test_file('test_model.stl')
        response = self.client.post('/submit', data={
            'student_name': 'John Smith',
            'student_email': 'john@example.com',
            'file': file,
            'printer': 'Prusa MK4S',
            'color': 'Blue'
        }, follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Submission Confirmed', response.data)
        
        # Get job and verify initial file location
        job = Job.query.first()
        self.assertIsNotNone(job)
        uploaded_path = self.test_jobs_root / Status.UPLOADED.value / job.filename
        self.assertTrue(uploaded_path.exists())
        
        # Staff approves job
        self.login_staff()
        response = self.client.post(f'/job/{job.id}/approve', data={
            'weight_g': 100,
            'time_min': 60,
            'printer': 'Prusa MK4S',
            'color': 'Blue',
            'material': 'PLA'
        }, follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        
        # Verify file moved to pending
        job = Job.query.get(job.id)
        self.assertEqual(job.status, Status.PENDING.value)
        pending_path = self.test_jobs_root / Status.PENDING.value / job.filename
        self.assertFalse(uploaded_path.exists())
        self.assertTrue(pending_path.exists())
        
        # Student confirms job
        token = job.confirm_url.split('/')[-1]
        response = self.client.post(f'/job/confirm/{token}', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        
        # Verify file moved to ready_to_print
        job = Job.query.get(job.id)
        self.assertEqual(job.status, Status.READY_TO_PRINT.value)
        ready_path = self.test_jobs_root / Status.READY_TO_PRINT.value / job.filename
        self.assertFalse(pending_path.exists())
        self.assertTrue(ready_path.exists())

    def test_file_rejection(self):
        """Test file handling during job rejection"""
        # Create and upload file
        file = self.create_test_file('test_model.stl')
        response = self.client.post('/submit', data={
            'student_name': 'John Smith',
            'student_email': 'john@example.com',
            'file': file,
            'printer': 'Prusa MK4S',
            'color': 'Blue'
        }, follow_redirects=True)
        
        job = Job.query.first()
        uploaded_path = self.test_jobs_root / Status.UPLOADED.value / job.filename
        
        # Staff rejects job
        self.login_staff()
        response = self.client.post(f'/job/{job.id}/reject', data={
            'reasons': ['Too large', 'Unsupported overhangs']
        }, follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        
        # Verify file moved to rejected
        job = Job.query.get(job.id)
        self.assertEqual(job.status, Status.REJECTED.value)
        rejected_path = self.test_jobs_root / Status.REJECTED.value / job.filename
        self.assertFalse(uploaded_path.exists())
        self.assertTrue(rejected_path.exists())

    def test_concurrent_file_operations(self):
        """Test concurrent file operations"""
        # Create test files
        source = self.test_jobs_root / 'test_source.stl'
        dest = self.test_jobs_root / 'test_dest.stl'
        
        with open(source, 'wb') as f:
            f.write(b'test content')
        
        # Perform atomic move
        atomic_move(source, dest)
        
        # Verify move was successful
        self.assertFalse(source.exists())
        self.assertTrue(dest.exists())
        with open(dest, 'rb') as f:
            self.assertEqual(f.read(), b'test content')

    def test_file_cleanup(self):
        """Test file cleanup when job is deleted"""
        # Create and upload file
        file = self.create_test_file('test_model.stl')
        response = self.client.post('/submit', data={
            'student_name': 'John Smith',
            'student_email': 'john@example.com',
            'file': file,
            'printer': 'Prusa MK4S',
            'color': 'Blue'
        }, follow_redirects=True)
        
        job = Job.query.first()
        file_path = self.test_jobs_root / Status.UPLOADED.value / job.filename
        self.assertTrue(file_path.exists())
        
        # Delete job
        db.session.delete(job)
        db.session.commit()
        
        # Verify file is removed
        self.assertFalse(file_path.exists())

if __name__ == '__main__':
    unittest.main() 