import os
from flask import Blueprint, request, jsonify
from models import Job
from extensions import db
from config import Config
from utils.file_utils import move_file_with_lock

move_bp = Blueprint('move', __name__)

@move_bp.route('/move/<int:job_id>/<to_status>', methods=['POST'])
def move(job_id, to_status):
    job = Job.query.get_or_404(job_id)
    src = os.path.join(Config.JOBS_ROOT, job.status, job.filename)
    dst = os.path.join(Config.JOBS_ROOT, to_status, job.filename)
    move_file_with_lock(src, dst)
    job.status = to_status
    db.session.commit()
    return jsonify(success=True) 