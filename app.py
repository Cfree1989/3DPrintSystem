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
from flask_migrate import Migrate
import logging
from logging.handlers import RotatingFileHandler

app = Flask(__name__, template_folder='Templates')
app.config.from_object(Config)

db.init_app(app)

migrate = Migrate(app, db)

# Ensure instance and job status folders exist
os.makedirs(Config.INSTANCE_DIR, exist_ok=True)
for folder in Config.STATUS_FOLDERS:
    os.makedirs(os.path.join(Config.JOBS_ROOT, folder), exist_ok=True)

# Register blueprints
app.register_blueprint(dashboard_bp)
app.register_blueprint(submit_bp)
app.register_blueprint(approval_bp)
app.register_blueprint(move_bp)
app.register_blueprint(file_bp)

if not app.debug:
    if not os.path.exists('logs'):
        os.mkdir('logs')
    file_handler = RotatingFileHandler('logs/app.log', maxBytes=10240, backupCount=10)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'))
    file_handler.setLevel(logging.INFO)
    app.logger.addHandler(file_handler)

    app.logger.setLevel(logging.INFO)
    app.logger.info('3DPrintSystem startup')

@app.after_request
def apply_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    # CSP updated to allow Tailwind CDN and inline scripts/styles
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "script-src 'self' https://cdn.tailwindcss.com 'unsafe-inline'; "
        "style-src 'self' https://cdn.tailwindcss.com 'unsafe-inline'; "
        "img-src 'self' data:"
    )
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # Consider adding HSTS if you plan to enforce HTTPS soon: 
    # response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

if __name__ == '__main__':
    app.run()
