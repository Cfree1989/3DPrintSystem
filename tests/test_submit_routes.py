import pytest
import os
from io import BytesIO
from app import app as flask_app # Use your actual app import
from models import Job # If you need to check Job model directly
from extensions import db # If you need to interact with db for setup/teardown
from unittest.mock import patch, MagicMock
from config import Config as AppConfig
import numpy as np

@pytest.fixture
def app():
    """Create and configure a new app instance for each test."""
    # 기본적인 Flask app 설정 (테스트용)
    flask_app.config.update({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", # Use in-memory SQLite for tests
        "WTF_CSRF_ENABLED": False, # Disable CSRF for simpler form testing if applicable
        "SECRET_KEY": "test-secret-key",
        # Ensure JOBS_ROOT and UPLOADED_FOLDER are set if your routes use them directly
        # You might need to mock Config.JOBS_ROOT or Config.UPLOADED_FOLDER if they are accessed
        # directly in the route logic and not via app.config
        "JOBS_ROOT": os.path.join(os.path.dirname(__file__), 'test_jobs_root'),
        "UPLOADED_FOLDER": "test_uploaded",
        "THUMBNAILS_DIR": os.path.join(os.path.dirname(__file__), 'test_thumbnails'),
        "BASE_DIR": os.path.join(os.path.dirname(__file__), '..')
    })

    # Create all database tables (for in-memory SQLite)
    with flask_app.app_context():
        db.create_all()
        # Create necessary test directories
        os.makedirs(os.path.join(flask_app.config["JOBS_ROOT"], flask_app.config["UPLOADED_FOLDER"]), exist_ok=True)
        os.makedirs(flask_app.config["THUMBNAILS_DIR"], exist_ok=True)

    yield flask_app

    # Clean up / Teardown
    with flask_app.app_context():
        db.drop_all()
    # Clean up test directories if needed (be careful with this)
    # shutil.rmtree(flask_app.config["JOBS_ROOT"], ignore_errors=True)
    # shutil.rmtree(flask_app.config["THUMBNAILS_DIR"], ignore_errors=True)

@pytest.fixture
def client(app):
    """A test client for the app."""
    return app.test_client()

# Example Test (can be removed or modified)
def test_example_route(client):
    response = client.get('/submit') # Assuming /submit is a GETtable route
    assert response.status_code == 200

def test_submit_form_get_request(client):
    """Test that a GET request to /submit returns the upload form."""
    response = client.get('/submit')
    assert response.status_code == 200
    assert b"3D Print File Submission" in response.data # Corrected assertion string

@patch('routes.submit_routes.Config') # Mock the Config object used in submit_routes
@patch('routes.submit_routes.trimesh')
@patch('routes.submit_routes.pyrender')
@patch('routes.submit_routes.Image')
@patch('os.makedirs') # Still mock os.makedirs if routes call it directly for thumbnails_dir
@patch('werkzeug.datastructures.FileStorage.save')
def test_submit_form_post_request_success(mock_save, mock_os_mkdirs_routes, mock_Image, mock_pyrender, mock_trimesh, mock_submit_routes_Config, client, app):
    """Test a successful POST request to /submit with valid data and a file."""
    
    # Configure the mock for Config used within submit_routes
    # This ensures that when submit_routes.Config.UPLOADED_FOLDER is accessed, it uses our test value.
    # Also mock BASE_DIR for thumbnail path construction if it's used via submit_routes.Config
    mock_submit_routes_Config.UPLOADED_FOLDER = app.config['UPLOADED_FOLDER'] # "test_uploaded"
    mock_submit_routes_Config.BASE_DIR = app.config['BASE_DIR'] # test environment's base_dir
    # If JOBS_ROOT is also from submit_routes.Config, mock it too:
    mock_submit_routes_Config.JOBS_ROOT = app.config['JOBS_ROOT']

    # Setup mock mesh object
    mock_mesh = MagicMock()
    mock_mesh.bounds.mean.return_value = np.array([0, 0, 0])
    mock_mesh.extents.max.return_value = 1.0
    mock_mesh.apply_translation = MagicMock()
    mock_trimesh.load.return_value = mock_mesh

    # Mock pyrender.OffscreenRenderer().render() to return dummy image data
    mock_renderer_instance = MagicMock()
    mock_renderer_instance.render.return_value = (np.zeros((100, 100, 3), dtype=np.uint8), np.zeros((100, 100), dtype=np.float32))
    mock_pyrender.OffscreenRenderer.return_value = mock_renderer_instance

    # Mock Image.fromarray().save()
    mock_pil_image = MagicMock()
    mock_Image.fromarray.return_value = mock_pil_image
    mock_pil_image.save = MagicMock()

    form_data = {
        'name': 'Test User',
        'email': 'test@example.com',
        'print_method': 'Filament',
        'print_color': 'Blue'
    }
    file_data = {
        'file': (BytesIO(b"my file contents"), 'test_file.stl')
    }

    response = client.post('/submit',
                           data={**form_data, **file_data},
                           content_type='multipart/form-data')

    assert response.status_code == 302
    assert response.headers['Location'] == '/submission-successful'

    with app.app_context():
        job = Job.query.filter_by(email='test@example.com').first()
        assert job is not None
        assert job.name == 'Test User'
        assert job.printer == 'Filament'
        assert job.color == 'Blue'
        # The filename now uses the mocked Config.UPLOADED_FOLDER via submit_routes
        assert job.filename.startswith('TestUser_Filament_Blue_1') 
        assert job.filename.endswith('.stl')
        # This assertion should now pass because submit_routes.Config.UPLOADED_FOLDER is mocked
        assert job.status == mock_submit_routes_Config.UPLOADED_FOLDER 

    mock_save.assert_called_once()
    mock_pil_image.save.assert_called_once() # Assert thumbnail save was attempted
    # Assert that os.makedirs for thumbnails_dir was called if it's conditional
    # Example: mock_os_mkdirs_routes.assert_any_call(app.config['THUMBNAILS_DIR'], exist_ok=True) 

def test_submit_form_post_no_file(client, app):
    """Test POST request to /submit without a file."""
    form_data = {
        'name': 'Test User',
        'email': 'test@example.com',
        'print_method': 'Filament',
        'print_color': 'Blue'
    }

    response = client.post('/submit',
                           data=form_data, # No file_data here
                           content_type='multipart/form-data')

    assert response.status_code == 200 # Should re-render the form
    # Check for flash message content in response data
    # This is a simple check; more robust flash testing can be done with `get_flashed_messages` in a test request context
    assert b"No file uploaded." in response.data 
    assert b"Please correct the errors below and resubmit." not in response.data # Example of checking for other potential messages

    # Verify no job was created
    with app.app_context():
        job = Job.query.filter_by(email='test@example.com').first()
        assert job is None

# More tests will go here for submit_routes 