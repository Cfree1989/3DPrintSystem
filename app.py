from flask import Flask
from config import Config
from extensions import db
from models import Job
from routes.dashboard_routes import dashboard_bp
from routes.submit_routes import submit_bp
from routes.approval_routes import approval_bp
from routes.move_routes import move_bp
from routes.file_routes import file_bp
import os

app = Flask(__name__, template_folder='Templates')
app.config.from_object(Config)

db.init_app(app)

# Ensure instance and job status folders exist
os.makedirs(Config.INSTANCE_DIR, exist_ok=True)
for folder in Config.STATUS_FOLDERS:
    os.makedirs(os.path.join(Config.JOBS_ROOT, folder), exist_ok=True)

@app.before_request
def create_tables():
    db.create_all()

# Register blueprints
app.register_blueprint(dashboard_bp)
app.register_blueprint(submit_bp)
app.register_blueprint(approval_bp)
app.register_blueprint(move_bp)
app.register_blueprint(file_bp)

if __name__ == '__main__':
    app.run()
