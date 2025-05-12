import unittest
import os
import io
from flask import url_for
from pathlib import Path
from app import create_app, db
# from app.models.user import User # Commented out
from app.models.job import Job, Status
from app.services.file_service import FileService
from config import TestingConfig
from werkzeug.datastructures import FileStorage

class TestFileManagement(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestingConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.create_all()
        
        # Create test user
        # self.user = User(username='testuser', email='test@example.com')
        # self.user.set_password('test_password')
        # db.session.add(self.user)
        # db.session.commit()
        
        # Log in the user
        self.client.post('/auth/login', data={
            'username': 'testuser',
            'password': 'test_password'
        })
        
        # Create test upload directory
        os.makedirs(self.app.config['UPLOAD_FOLDER'], exist_ok=True)

    def tearDown(self):
        # Clean up uploaded files
        for root, dirs, files in os.walk(self.app.config['UPLOAD_FOLDER']):
            for file in files:
                os.remove(os.path.join(root, file))
        os.rmdir(self.app.config['UPLOAD_FOLDER'])
        
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def create_test_file(self, filename, content=b'test file content'):
        return FileStorage(
            stream=io.BytesIO(content),
            filename=filename,
            content_type='application/octet-stream'
        )

    def test_valid_file_upload(self):
        """Test uploading a valid 3D model file"""
        file = self.create_test_file('test_model.stl')
        response = self.client.post('/upload', data={
            'file': file,
            'printer': 'Prusa MK4S',
            'color': 'Blue'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'File uploaded successfully', response.data)
        
        # Check database record
        job = Job.query.filter_by(user_id=self.user.id).first()
        self.assertIsNotNone(job)
        self.assertEqual(job.status, Status.UPLOADED)
        
        # Check file exists
        file_path = os.path.join(self.app.config['UPLOAD_FOLDER'], job.filename)
        self.assertTrue(os.path.exists(file_path))

    def test_invalid_file_extension(self):
        """Test uploading a file with invalid extension"""
        file = self.create_test_file('invalid.txt')
        response = self.client.post('/upload', data={
            'file': file,
            'printer': 'Prusa MK4S',
            'color': 'Blue'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Invalid file type', response.data)

    def test_file_size_limit(self):
        """Test file size limit"""
        # Create a file larger than the limit
        large_content = b'x' * (self.app.config['MAX_CONTENT_LENGTH'] + 1)
        file = self.create_test_file('large.stl', large_content)
        response = self.client.post('/upload', data={
            'file': file,
            'printer': 'Prusa MK4S',
            'color': 'Blue'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 413)  # Request Entity Too Large

    def test_file_status_transition(self):
        """Test file status transitions"""
        # Upload file
        file = self.create_test_file('test_model.stl')
        self.client.post('/upload', data={
            'file': file,
            'printer': 'Prusa MK4S',
            'color': 'Blue'
        })
        
        job = Job.query.filter_by(user_id=self.user.id).first()
        original_filename = job.filename
        
        # Create staff user
        staff = User(username='staff', email='staff@example.com', role='staff')
        staff.set_password('staff_password')
        db.session.add(staff)
        db.session.commit()
        
        # Login as staff
        self.client.get('/auth/logout')
        self.client.post('/auth/login', data={
            'username': 'staff',
            'password': 'staff_password'
        })
        
        # Approve job
        response = self.client.post(f'/job/{job.id}/approve', data={
            'weight_g': 100,
            'time_min': 60
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        
        # Check status changed
        job = Job.query.get(job.id)
        self.assertEqual(job.status, Status.PENDING)
        
        # Check file moved to new location
        old_path = os.path.join(self.app.config['UPLOAD_FOLDER'], 'uploaded', original_filename)
        new_path = os.path.join(self.app.config['UPLOAD_FOLDER'], 'pending', job.filename)
        self.assertFalse(os.path.exists(old_path))
        self.assertTrue(os.path.exists(new_path))

    def test_concurrent_file_operations(self):
        """Test concurrent file operations"""
        # This would require a more sophisticated test setup with multiple threads
        # For now, we'll just verify our atomic move operation works
        from app.services.file_service import atomic_move
        from pathlib import Path
        
        # Create test files
        source = Path(self.app.config['UPLOAD_FOLDER']) / 'test_source.stl'
        dest = Path(self.app.config['UPLOAD_FOLDER']) / 'test_dest.stl'
        
        with open(source, 'wb') as f:
            f.write(b'test content')
        
        # Perform atomic move
        atomic_move(source, dest)
        
        self.assertFalse(source.exists())
        self.assertTrue(dest.exists())
        with open(dest, 'rb') as f:
            self.assertEqual(f.read(), b'test content')

if __name__ == '__main__':
    unittest.main() 