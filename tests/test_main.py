import os
import unittest
from io import BytesIO
from app import create_app, db
from app.models.user import User
from app.models.job import Job, Status
from config import Config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite://'
    WTF_CSRF_ENABLED = False
    UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'test_uploads')

class MainTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestConfig)
        self.client = self.app.test_client()
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()
        
        # Create test user
        user = User(username='test_user', email='test@example.com')
        user.set_password('test_password')
        db.session.add(user)
        
        # Create staff user
        staff = User(username='staff_user', email='staff@example.com', is_staff=True)
        staff.set_password('staff_password')
        db.session.add(staff)
        
        db.session.commit()
        
        # Create upload directory
        os.makedirs(os.path.join(TestConfig.UPLOAD_FOLDER, 'uploaded'), exist_ok=True)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
        # Clean up test upload directory
        import shutil
        if os.path.exists(TestConfig.UPLOAD_FOLDER):
            shutil.rmtree(TestConfig.UPLOAD_FOLDER)

    def login(self, username, password):
        return self.client.post('/auth/login', data={
            'username': username,
            'password': password
        }, follow_redirects=True)

    def test_index_redirect_if_not_logged_in(self):
        response = self.client.get('/')
        self.assertEqual(response.status_code, 302)
        self.assertTrue('/auth/login' in response.location)

    def test_index_if_logged_in(self):
        self.login('test_user', 'test_password')
        response = self.client.get('/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b'Upload New Print' in response.data)

    def test_upload_file(self):
        self.login('test_user', 'test_password')
        
        # Create a test file
        data = {
            'file': (BytesIO(b'test file content'), 'test.stl'),
            'printer': 'Prusa MK4S',
            'color': 'Black'
        }
        
        response = self.client.post('/upload', data=data, follow_redirects=True,
                                  content_type='multipart/form-data')
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b'File uploaded successfully' in response.data)
        
        # Check if job was created
        job = Job.query.first()
        self.assertIsNotNone(job)
        self.assertEqual(job.status, Status.UPLOADED)
        self.assertEqual(job.printer, 'Prusa MK4S')
        self.assertEqual(job.color, 'Black')

    def test_jobs_list(self):
        self.login('test_user', 'test_password')
        
        # Create a test job
        user = User.query.filter_by(username='test_user').first()
        job = Job(user_id=user.id,
                 filename='test_job.stl',
                 original_filename='test.stl',
                 printer='Prusa MK4S',
                 color='Black')
        db.session.add(job)
        db.session.commit()
        
        response = self.client.get('/jobs')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b'test.stl' in response.data)
        self.assertTrue(b'Prusa MK4S' in response.data)
        self.assertTrue(b'Black' in response.data)

    def test_pending_jobs_staff_only(self):
        # Test access denied for regular user
        self.login('test_user', 'test_password')
        response = self.client.get('/pending-jobs')
        self.assertEqual(response.status_code, 302)  # Redirected
        
        # Test access granted for staff
        self.login('staff_user', 'staff_password')
        response = self.client.get('/pending-jobs')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b'Print Queue' in response.data)

    def test_approve_job(self):
        self.login('staff_user', 'staff_password')
        
        # Create a test job
        user = User.query.filter_by(username='test_user').first()
        job = Job(user_id=user.id,
                 filename='test_job.stl',
                 original_filename='test.stl',
                 printer='Prusa MK4S',
                 color='Black')
        db.session.add(job)
        db.session.commit()
        
        # Approve the job
        response = self.client.post('/approve', data={
            'job_id': job.id,
            'weight': 100,  # 100g
            'time': 2  # 2 hours
        }, follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b'Job approved' in response.data)
        
        # Check job status and calculations
        job = Job.query.get(job.id)
        self.assertEqual(job.status, Status.PENDING)
        self.assertEqual(job.weight_g, 100)
        self.assertEqual(job.time_min, 120)  # 2 hours = 120 minutes
        self.assertIsNotNone(job.cost)

    def test_reject_job(self):
        self.login('staff_user', 'staff_password')
        
        # Create a test job
        user = User.query.filter_by(username='test_user').first()
        job = Job(user_id=user.id,
                 filename='test_job.stl',
                 original_filename='test.stl',
                 printer='Prusa MK4S',
                 color='Black')
        db.session.add(job)
        db.session.commit()
        
        # Reject the job
        response = self.client.post('/reject', data={
            'job_id': job.id,
            'reasons': ['Too large', 'Unsupported overhangs']
        }, follow_redirects=True)
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b'Job rejected' in response.data)
        
        # Check job status and notes
        job = Job.query.get(job.id)
        self.assertEqual(job.status, Status.REJECTED)
        self.assertTrue('Too large' in job.notes)
        self.assertTrue('Unsupported overhangs' in job.notes)

if __name__ == '__main__':
    unittest.main() 