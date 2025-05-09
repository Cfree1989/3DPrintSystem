import os
from flask import Blueprint, request, url_for, redirect, render_template, jsonify, flash
from models import Job
from extensions import db
from config import Config
from utils.file_utils import move_file_with_lock
from email_util import send_email

approval_bp = Blueprint('approval', __name__)

@approval_bp.route('/approve', methods=['POST'])
def approve():
    job_id = request.form.get('job_id')
    job = Job.query.get_or_404(int(job_id))

    job.weight = float(request.form.get('weight', 0))
    job.time_hours = int(request.form.get('time_hours', 0))
    job.time_minutes = int(request.form.get('time_minutes', 0))
    job.printer = request.form.get('printer')
    # Calculate cost
    if job.printer and 'formlabs' in job.printer.lower():
        job.cost = job.weight * 0.20
    else:
        job.cost = job.weight * 0.10

    # Move file: Uploaded -> Pending
    src = os.path.join(Config.JOBS_ROOT, Config.UPLOADED_FOLDER, job.filename)
    dst = os.path.join(Config.JOBS_ROOT, Config.PENDING_FOLDER, job.filename)
    move_file_with_lock(src, dst)
    job.status = Config.PENDING_FOLDER
    db.session.commit()

    # Send confirmation email to student
    link = url_for('approval.confirm_print', job_id=job.id, _external=True)
    body = f"""Your print request is almost ready. Please confirm here:\n\n{link}\n\nCost: ${job.cost:.2f}\nTime: {job.time_hours}h {job.time_minutes}m\nColor: {job.color or 'N/A'}\nMaterial: {job.material or 'N/A'}"""
    send_email(job.email, "Confirm your 3D print request", body)
    flash('Print approved and student notified for confirmation.', 'success')
    return redirect(url_for('dashboard.dashboard'))

@approval_bp.route('/confirm_print/<int:job_id>', methods=['GET', 'POST'])
def confirm_print(job_id):
    job = Job.query.get_or_404(job_id)
    if job.student_confirmed:
        return render_template('Confirmation/confirmation_already.html', job=job)
    if request.method == 'POST':
        # Move file: Pending -> ReadyToPrint
        src = os.path.join(Config.JOBS_ROOT, Config.PENDING_FOLDER, job.filename)
        dst = os.path.join(Config.JOBS_ROOT, Config.READY_TO_PRINT_FOLDER, job.filename)
        move_file_with_lock(src, dst)
        job.status = Config.READY_TO_PRINT_FOLDER
        job.student_confirmed = True
        db.session.commit()
        flash('Print confirmed and moved to Ready to Print.', 'success')
        return redirect(url_for('dashboard.dashboard'))
    return render_template('Confirmation/confirmation.html', job=job)

@approval_bp.route('/reject', methods=['POST'])
def reject():
    job_id = request.form.get('job_id')
    job = Job.query.get_or_404(int(job_id))
    reasons = request.form.getlist('reasons')
    job.rejection_reasons = '; '.join(reasons)

    src = os.path.join(Config.JOBS_ROOT, Config.UPLOADED_FOLDER, job.filename)
    dst = os.path.join(Config.JOBS_ROOT, Config.REJECTED_FOLDER, job.filename)
    move_file_with_lock(src, dst)
    job.status = Config.REJECTED_FOLDER
    db.session.commit()

    body = "Your 3D print request was rejected for these reasons:\n\n" + "\n".join(f"- {r}" for r in reasons)
    send_email(job.email, "Your print request was rejected", body)
    flash('Print rejected and student notified.', 'success')
    return jsonify(success=True) 