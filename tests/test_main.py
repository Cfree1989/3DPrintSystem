import os
import unittest
from io import BytesIO
from app import create_app, db
from app.models.job import Job, Status
from config import TestingConfig

class MainTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestingConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.create_all()
        
        # Create test directories
        self.test_jobs_root = os.path.join(self.app.config['JOBS_ROOT'])
        for folder in self.app.config['STATUS_FOLDERS']:
            os.makedirs(os.path.join(self.test_jobs_root, folder), exist_ok=True)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        # Clean up test directories
        if os.path.exists(self.test_jobs_root):
            import shutil
            shutil.rmtree(self.test_jobs_root)
        self.app_context.pop()

    def login_staff(self):
        """Helper method to log in as staff"""
        return self.client.post('/staff/login', data={
            'password': self.app.config['STAFF_PASSWORD']
        }, follow_redirects=True)

    def test_index_redirect_to_submit(self):
        """Test that index redirects to submit page"""
        response = self.client.get('/')
        self.assertEqual(response.status_code, 302)
        self.assertTrue('/submit' in response.location)

    def test_submit_page_public_access(self):
        """Test that submit page is publicly accessible"""
        response = self.client.get('/submit')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b'Submit a Print Job' in response.data)

    def test_staff_login(self):
        """Test staff login functionality"""
        # Test invalid password
        response = self.client.post('/staff/login', data={
            'password': 'wrong_password'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b'Invalid password' in response.data)
        
        # Test valid password
        response = self.login_staff()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b'Dashboard' in response.data)

    def test_staff_logout(self):
        """Test staff logout functionality"""
        # Login first
        self.login_staff()
        
        # Test logout
        response = self.client.get('/staff/logout', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b'You have been logged out' in response.data)
        
        # Verify can't access protected routes after logout
        response = self.client.get('/dashboard')
        self.assertEqual(response.status_code, 302)
        self.assertTrue('/staff/login' in response.location)

    def test_dashboard_staff_only(self):
        """Test dashboard access is staff-only"""
        # Test without login
        response = self.client.get('/dashboard')
        self.assertEqual(response.status_code, 302)
        self.assertTrue('/staff/login' in response.location)
        
        # Test with staff login
        self.login_staff()
        response = self.client.get('/dashboard')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b'Dashboard' in response.data)

    def test_job_submission(self):
        """Test job submission process"""
        data = {
            'student_name': 'John Smith',
            'student_email': 'john@example.com',
            'file': (BytesIO(b'test file content'), 'test.stl'),
            'printer': 'Prusa MK4S',
            'color': 'Black'
        }
        
        response = self.client.post('/submit', 
                                  data=data, 
                                  follow_redirects=True,
                                  content_type='multipart/form-data')
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue(b'Submission Confirmed' in response.data)
        
        # Check job was created correctly
        job = Job.query.first()
        self.assertIsNotNone(job)
        self.assertEqual(job.status, Status.UPLOADED.value)
        self.assertEqual(job.student_name, 'John Smith')
        self.assertEqual(job.student_email, 'john@example.com')
        self.assertEqual(job.printer, 'Prusa MK4S')
        self.assertEqual(job.color, 'Black')
        self.assertTrue(job.filename.startswith('JohnSmith_PrusaMK4S_Black_'))
        self.assertTrue(job.filename.endswith('.stl'))

    def test_job_approval_staff_only(self):
        """Test that job approval requires staff login"""
        # Create a test job
        job = Job(
            student_name='John Smith',
            student_email='john@example.com',
            filename='test.stl',
            original_filename='test.stl',
            status=Status.UPLOADED,
            printer='Prusa MK4S',
            color='Blue'
        )
        db.session.add(job)
        db.session.commit()

        # Try to approve without staff login
        response = self.client.post(f'/job/{job.id}/approve', data={
            'weight_g': 100,
            'time_min': 120,
            'printer': 'Prusa MK4S',
            'color': 'Blue',
            'material': 'PLA'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Please log in as staff', response.data)

        # Login as staff
        self.login_staff()

        # Try to approve with staff login
        response = self.client.post(f'/job/{job.id}/approve', data={
            'weight_g': 100,
            'time_min': 120,
            'printer': 'Prusa MK4S',
            'color': 'Blue',
            'material': 'PLA'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Job approved', response.data)

        # Check job status
        job = Job.query.get(job.id)
        self.assertEqual(job.status, Status.PENDING.value)
        self.assertIsNotNone(job.confirm_url)

    def test_job_rejection_staff_only(self):
        """Test that job rejection requires staff login"""
        # Create a test job
        job = Job(
            student_name='John Smith',
            student_email='john@example.com',
            filename='test.stl',
            original_filename='test.stl',
            status=Status.UPLOADED,
            printer='Prusa MK4S',
            color='Blue'
        )
        db.session.add(job)
        db.session.commit()

        # Try to reject without staff login
        response = self.client.post(f'/job/{job.id}/reject', data={
            'reasons': ['Too large', 'Unsupported overhangs']
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Please log in as staff', response.data)

        # Login as staff
        self.login_staff()

        # Try to reject with staff login
        response = self.client.post(f'/job/{job.id}/reject', data={
            'reasons': ['Too large', 'Unsupported overhangs']
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Job rejected', response.data)

        # Check job status and rejection reasons
        job = Job.query.get(job.id)
        self.assertEqual(job.status, Status.REJECTED.value)
        self.assertEqual(job.reject_reasons, ['Too large', 'Unsupported overhangs'])

if __name__ == '__main__':
    unittest.main() 