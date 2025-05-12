import unittest
from app import create_app, db
from app.models.user import User
from config import TestingConfig

class TestAuth(unittest.TestCase):
    def setUp(self):
        self.app = create_app(TestingConfig)
        self.app_context = self.app.app_context()
        self.app_context.push()
        self.client = self.app.test_client()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_password_hashing(self):
        u = User(username='test', email='test@example.com')
        u.set_password('test_password')
        self.assertFalse(u.check_password('wrong_password'))
        self.assertTrue(u.check_password('test_password'))

    def test_user_registration(self):
        response = self.client.post('/auth/register', data={
            'username': 'testuser',
            'email': 'testuser@example.com',
            'password': 'testpass123',
            'password2': 'testpass123'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        user = User.query.filter_by(username='testuser').first()
        self.assertIsNotNone(user)
        self.assertEqual(user.email, 'testuser@example.com')

    def test_login_logout(self):
        # Create a test user
        user = User(username='testuser', email='testuser@example.com')
        user.set_password('testpass123')
        db.session.add(user)
        db.session.commit()

        # Test login
        response = self.client.post('/auth/login', data={
            'username': 'testuser',
            'password': 'testpass123',
            'remember_me': False
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)

        # Test logout
        response = self.client.get('/auth/logout', follow_redirects=True)
        self.assertEqual(response.status_code, 200)

    def test_invalid_login(self):
        response = self.client.post('/auth/login', data={
            'username': 'nonexistent',
            'password': 'wrongpass',
            'remember_me': False
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Invalid username or password', response.data)

    def test_duplicate_username(self):
        # Create first user
        user1 = User(username='testuser', email='test1@example.com')
        user1.set_password('test123')
        db.session.add(user1)
        db.session.commit()

        # Try to create second user with same username
        response = self.client.post('/auth/register', data={
            'username': 'testuser',
            'email': 'test2@example.com',
            'password': 'test123',
            'password2': 'test123'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Please use a different username', response.data)

if __name__ == '__main__':
    unittest.main() 