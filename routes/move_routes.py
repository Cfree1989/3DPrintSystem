import os
from flask import Blueprint, request, jsonify, flash
from models import Job
from extensions import db
from config import Config
from utils.file_utils import move_file_with_lock
from email_util import send_email

move_bp = Blueprint('move', __name__)

@move_bp.route('/move/<int:job_id>/<to_status>', methods=['POST'])
def move(job_id, to_status):
    job = Job.query.get_or_404(job_id)
    src = os.path.join(Config.JOBS_ROOT, job.status, job.filename)
    dst = os.path.join(Config.JOBS_ROOT, to_status, job.filename)
    move_file_with_lock(src, dst)
    job.status = to_status
    db.session.commit()
    if to_status == 'Completed':
        send_email(job.email, 'Your 3D print is completed!', 'Your 3D print job has been completed and is ready for pickup.')
        flash('Student notified: print marked as completed.', 'success')
    else:
        flash(f'Print moved to {to_status}.', 'success')
    return jsonify(success=True) 