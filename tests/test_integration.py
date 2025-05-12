import unittest
from flask import url_for
from flask_mail import Message
from app import create_app, db
# from app.models.user import User # Commented out
from app.models.job import Job
from config import TestingConfig
import re

class TestUserFlows(unittest.TestCase):
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

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()
        self.sent_emails = []

    def test_registration_and_login_flow(self):
        """Test the complete flow from registration to login"""
        # 1. Register a new user
        response = self.client.post('/auth/register', data={
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'test_password',
            'password2': 'test_password'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Congratulations, you are now a registered user!', response.data)
        
        # 2. Try to log in with wrong password
        response = self.client.post('/auth/login', data={
            'username': 'testuser',
            'password': 'wrong_password',
            'remember_me': False
        }, follow_redirects=True)
        self.assertIn(b'Invalid username or password', response.data)
        
        # 3. Log in with correct password
        response = self.client.post('/auth/login', data={
            'username': 'testuser',
            'password': 'test_password',
            'remember_me': True
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        
        # 4. Access protected page
        response = self.client.get('/dashboard')
        self.assertEqual(response.status_code, 200)
        
        # 5. Logout
        response = self.client.get('/auth/logout', follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        
        # 6. Try to access protected page after logout
        response = self.client.get('/dashboard')
        self.assertEqual(response.status_code, 302)  # Redirects to login

    def test_password_reset_flow(self):
        """Test the complete password reset flow"""
        # 1. Create a user
        user = User(username='resetuser', email='reset@example.com')
        user.set_password('original_password')
        db.session.add(user)
        db.session.commit()
        
        # 2. Request password reset
        response = self.client.post('/auth/reset-password-request', data={
            'email': 'reset@example.com'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(self.sent_emails), 1)
        
        # Extract token from email
        email_body = self.sent_emails[0].html
        token_match = re.search(r'/reset-password/([^"]+)', email_body)
        self.assertIsNotNone(token_match)
        token = token_match.group(1)
        
        # 3. Reset password with token
        response = self.client.post(f'/auth/reset-password/{token}', data={
            'password': 'new_password',
            'password2': 'new_password'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Your password has been reset', response.data)
        
        # 4. Try to log in with old password
        response = self.client.post('/auth/login', data={
            'username': 'resetuser',
            'password': 'original_password'
        }, follow_redirects=True)
        self.assertIn(b'Invalid username or password', response.data)
        
        # 5. Log in with new password
        response = self.client.post('/auth/login', data={
            'username': 'resetuser',
            'password': 'new_password'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)

    def test_duplicate_registration(self):
        """Test registration with duplicate username/email"""
        # 1. Create initial user
        response = self.client.post('/auth/register', data={
            'username': 'testuser',
            'email': 'test@example.com',
            'password': 'test_password',
            'password2': 'test_password'
        }, follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        
        # 2. Try to register with same username
        response = self.client.post('/auth/register', data={
            'username': 'testuser',
            'email': 'different@example.com',
            'password': 'test_password',
            'password2': 'test_password'
        }, follow_redirects=True)
        self.assertIn(b'Please use a different username', response.data)
        
        # 3. Try to register with same email
        response = self.client.post('/auth/register', data={
            'username': 'different',
            'email': 'test@example.com',
            'password': 'test_password',
            'password2': 'test_password'
        }, follow_redirects=True)
        self.assertIn(b'Please use a different email address', response.data)

if __name__ == '__main__':
    unittest.main() 