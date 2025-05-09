import os

class Config:
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    INSTANCE_DIR = os.path.join(BASE_DIR, 'instance')
    DB_PATH = os.path.join(INSTANCE_DIR, 'jobs.db')
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + DB_PATH
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'your-default-secret-key-for-dev'

    JOBS_ROOT = os.path.join(BASE_DIR, 'jobs')
    UPLOADED_FOLDER = 'Uploaded'
    PENDING_FOLDER = 'Pending'
    REJECTED_FOLDER = 'Rejected'
    READY_TO_PRINT_FOLDER = 'ReadyToPrint'
    PRINTING_FOLDER = 'Printing'
    COMPLETED_FOLDER = 'Completed'
    PAID_PICKED_UP_FOLDER = 'PaidPickedUp'

    STATUS_FOLDERS = [
        UPLOADED_FOLDER, PENDING_FOLDER, REJECTED_FOLDER,
        READY_TO_PRINT_FOLDER, PRINTING_FOLDER, COMPLETED_FOLDER,
        PAID_PICKED_UP_FOLDER
    ] 