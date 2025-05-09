import os
from flask import Blueprint, send_file, abort, current_app
from werkzeug.utils import safe_join
from models import Job
from config import Config

file_bp = Blueprint('file', __name__)

@file_bp.route('/open_file/<int:job_id>')
def open_file(job_id):
    job = Job.query.get_or_404(job_id)
    # Build path to the file in its current status folder
    path = os.path.join(Config.JOBS_ROOT, job.status, job.filename)
    if not os.path.exists(path):
        abort(404)
    # Let Flask send it inline in the browser
    return send_file(path, as_attachment=False)

@file_bp.route('/thumbnail/<filename>')
def serve_thumbnail(filename):
    # current_app.root_path is the 'app' directory.
    # Thumbnails are saved in 'app/thumbnails/'
    thumbnails_dir = os.path.join(current_app.root_path, 'thumbnails')
    path = safe_join(thumbnails_dir, filename)
    if not os.path.exists(path):
        print(f"DEBUG: Thumbnail not found at path: {path}") # Added for debugging
        abort(404)
    return send_file(path, mimetype='image/png') 