import os
from datetime import timedelta

class Config:
    # Base paths
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    INSTANCE_DIR = os.path.join(BASE_DIR, 'instance')
    JOBS_ROOT = os.path.join(BASE_DIR, 'jobs')
    
    # Status folders
    UPLOADED_FOLDER = 'Uploaded'
    PENDING_FOLDER = 'Pending'
    REJECTED_FOLDER = 'Rejected'
    READY_TO_PRINT_FOLDER = 'ReadyToPrint'
    PRINTING_FOLDER = 'Printing'
    COMPLETED_FOLDER = 'Completed'
    PAID_PICKED_UP_FOLDER = 'PaidPickedUp'
    
    STATUS_FOLDERS = [
        UPLOADED_FOLDER,
        PENDING_FOLDER,
        REJECTED_FOLDER,
        READY_TO_PRINT_FOLDER,
        PRINTING_FOLDER,
        COMPLETED_FOLDER,
        PAID_PICKED_UP_FOLDER
    ]
    
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-please-change-in-production'
    
    # Database
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///app.db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # File Upload
    UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'uploads')
    MAX_CONTENT_LENGTH = 50 * 1024 * 1024  # 50MB max file size
    ALLOWED_EXTENSIONS = {'stl', 'obj', '3mf'}
    
    # Email Configuration
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'localhost')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 8025))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', False)
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'noreply@3dprint.local')
    
    # Session Configuration
    PERMANENT_SESSION_LIFETIME = timedelta(days=7)
    
    # Maintenance
    MAINTENANCE_FOLDER = os.path.join(BASE_DIR, 'maintenance')
    DISK_SPACE_THRESHOLD = 0.9  # 90% disk usage threshold
    
    # Create required directories
    @staticmethod
    def init_app(app):
        # Create upload directories
        os.makedirs(os.path.join(Config.UPLOAD_FOLDER, 'uploaded'), exist_ok=True)
        os.makedirs(os.path.join(Config.UPLOAD_FOLDER, 'processed'), exist_ok=True)
        os.makedirs(os.path.join(Config.UPLOAD_FOLDER, 'archived'), exist_ok=True)
        
        # Create instance directory
        os.makedirs(Config.INSTANCE_DIR, exist_ok=True)
        
        # Create job status directories
        for folder in Config.STATUS_FOLDERS:
            os.makedirs(os.path.join(Config.JOBS_ROOT, folder), exist_ok=True)
        
        # Create maintenance directory
        os.makedirs(Config.MAINTENANCE_FOLDER, exist_ok=True)

class DevelopmentConfig(Config):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.environ.get('DEV_DATABASE_URL') or 'sqlite:///dev.db'

class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite://'  # Use in-memory database
    WTF_CSRF_ENABLED = False
    UPLOAD_FOLDER = os.path.join(os.path.abspath(os.path.dirname(__file__)), 'test_uploads')

class ProductionConfig(Config):
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL')
    
    @classmethod
    def init_app(cls, app):
        Config.init_app(app)
        
        # Production specific setup
        import logging
        from logging.handlers import RotatingFileHandler
        
        # Ensure log directory exists
        if not os.path.exists('logs'):
            os.mkdir('logs')
        
        # Set up production logging
        file_handler = RotatingFileHandler('logs/3dprint.log',
                                         maxBytes=10240,
                                         backupCount=10)
        file_handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s '
            '[in %(pathname)s:%(lineno)d]'
        ))
        file_handler.setLevel(logging.INFO)
        app.logger.addHandler(file_handler)
        app.logger.setLevel(logging.INFO)
        app.logger.info('3D Print System startup')

config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
} 