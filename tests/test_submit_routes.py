import pytest
import os
from io import BytesIO
from app import create_app
from flask import url_for
from werkzeug.datastructures import FileStorage
from app.models.job import Job, Status
from extensions import db
from unittest.mock import patch, MagicMock
from config import TestingConfig
import numpy as np

@pytest.fixture
def app():
    """Create and configure a new app instance for each test."""
    app = create_app(TestingConfig)
    app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
        "WTF_CSRF_ENABLED": False,
        "SECRET_KEY": "test-secret-key",
        "JOBS_ROOT": os.path.join(os.path.dirname(__file__), 'test_jobs_root'),
        "UPLOADED_FOLDER": "test_uploaded",
        "THUMBNAILS_DIR": os.path.join(os.path.dirname(__file__), 'test_thumbnails'),
        "BASE_DIR": os.path.join(os.path.dirname(__file__), '..')
    })

    with app.app_context():
        db.create_all()
        # Create necessary test directories
        os.makedirs(os.path.join(app.config["JOBS_ROOT"], app.config["UPLOADED_FOLDER"]), exist_ok=True)
        os.makedirs(app.config["THUMBNAILS_DIR"], exist_ok=True)

    yield app

    with app.app_context():
        db.drop_all()
        # Clean up test directories
        import shutil
        shutil.rmtree(app.config["JOBS_ROOT"], ignore_errors=True)
        shutil.rmtree(app.config["THUMBNAILS_DIR"], ignore_errors=True)

@pytest.fixture
def client(app):
    """Create a test client for the app."""
    return app.test_client()

@pytest.fixture
def runner(app):
    """Create a test CLI runner for the app."""
    return app.test_cli_runner()

@pytest.fixture
def test_file():
    """Create a test file for upload."""
    return FileStorage(
        stream=BytesIO(b"test content"),
        filename="test.stl",
        content_type="application/octet-stream",
    )

def test_submit_form_get(client):
    """Test GET request to /submit."""
    response = client.get('/submit')
    assert response.status_code == 200
    assert b'Submit a Print Job' in response.data

@pytest.mark.usefixtures('app')
def test_submit_form_post_request_success(app, client):
    """Test successful POST request to /submit."""
    with app.app_context():
        form_data = {
            'student_name': 'John Smith',
            'student_email': 'john@example.com',
            'printer': 'Prusa MK4S',
            'color': 'Blue'
        }
        
        # Create a new BytesIO for each request
        file_data = {
            'file': (BytesIO(b"test content"), 'test.stl')
        }

        response = client.post('/submit',
                             data={**form_data, **file_data},
                             content_type='multipart/form-data',
                             follow_redirects=True)

        assert response.status_code == 200
        assert b'Submission Confirmed' in response.data

        job = Job.query.filter_by(student_email='john@example.com').first()
        assert job is not None
        assert job.student_name == 'John Smith'
        assert job.status == Status.UPLOADED.value
        assert job.printer == 'Prusa MK4S'
        assert job.color == 'Blue'

@pytest.mark.usefixtures('app')
def test_submit_form_post_no_file(app, client):
    """Test POST request to /submit without a file."""
    with app.app_context():
        form_data = {
            'student_name': 'John Smith',
            'student_email': 'john@example.com',
            'printer': 'Prusa MK4S',
            'color': 'Blue'
        }

        response = client.post('/submit',
                             data=form_data,
                             content_type='multipart/form-data',
                             follow_redirects=True)

        assert response.status_code == 200
        assert b'No file selected' in response.data

        job = Job.query.filter_by(student_email='john@example.com').first()
        assert job is None

@pytest.mark.usefixtures('app')
def test_submit_form_post_invalid_file_type(app, client):
    """Test POST request to /submit with an invalid file type."""
    with app.app_context():
        form_data = {
            'student_name': 'John Smith',
            'student_email': 'john@example.com',
            'printer': 'Prusa MK4S',
            'color': 'Blue'
        }
        
        # Create a new BytesIO for each request
        file_data = {
            'file': (BytesIO(b"not a 3D model"), 'test.txt')
        }

        response = client.post('/submit',
                             data={**form_data, **file_data},
                             content_type='multipart/form-data',
                             follow_redirects=True)

        assert response.status_code == 200
        assert b'Invalid file type' in response.data

        job = Job.query.filter_by(student_email='john@example.com').first()
        assert job is None

@pytest.mark.usefixtures('app')
def test_submit_form_missing_required_fields(app, client):
    """Test POST request to /submit with missing required fields."""
    with app.app_context():
        # Test missing student name
        form_data = {
            'student_email': 'john@example.com',
            'printer': 'Prusa MK4S',
            'color': 'Blue'
        }
        
        # Create a new BytesIO for each request
        file_data = {
            'file': (BytesIO(b"test content"), 'test.stl')
        }

        response = client.post('/submit',
                             data={**form_data, **file_data},
                             content_type='multipart/form-data',
                             follow_redirects=True)

        assert response.status_code == 200
        assert b'Student name and email are required' in response.data

        # Test missing email
        form_data = {
            'student_name': 'John Smith',
            'printer': 'Prusa MK4S',
            'color': 'Blue'
        }

        # Create a new BytesIO for each request
        file_data = {
            'file': (BytesIO(b"test content"), 'test.stl')
        }

        response = client.post('/submit',
                             data={**form_data, **file_data},
                             content_type='multipart/form-data',
                             follow_redirects=True)

        assert response.status_code == 200
        assert b'Student name and email are required' in response.data

# More tests will go here for submit_routes 