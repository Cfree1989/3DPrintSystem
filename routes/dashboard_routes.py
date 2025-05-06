from flask import Blueprint, render_template
from models import Job
from config import Config

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@dashboard_bp.route('/dashboard')
def dashboard():
    statuses = Config.STATUS_FOLDERS + [Config.REJECTED_FOLDER]
    jobs_by_status = {status: Job.query.filter_by(status=status).all() for status in statuses}
    return render_template('dashboard.html', jobs_by_status=jobs_by_status) 