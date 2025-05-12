from flask import Blueprint, render_template, flash, redirect, url_for, request, current_app, send_file, jsonify, abort
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.models.job import Job, Status
from app.models.user import User
from app import db
from app.services.file_service import FileService
from app.services.thumbnail_service import ThumbnailService
from app.services.email_service import EmailService
import os
from datetime import datetime
from pathlib import Path

main = Blueprint('main', __name__)

@main.route('/')
@main.route('/index')
@login_required
def index():
    return render_template('main/index.html', title='Home')

@main.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file selected', 'error')
            return redirect(request.url)
        
        file = request.files['file']
        if file.filename == '':
            flash('No file selected', 'error')
            return redirect(request.url)
            
        if not FileService.allowed_file(file.filename):
            flash('Invalid file type. Allowed types: ' + ', '.join(FileService.ALLOWED_EXTENSIONS), 'error')
            return redirect(request.url)
            
        # Generate secure filename
        original_filename = file.filename
        filename = FileService.secure_job_filename(
            username=current_user.username,
            printer=request.form.get('printer', ''),
            color=request.form.get('color', ''),
            original_filename=original_filename
        )
        
        # Create job record
        job = Job(
            user_id=current_user.id,
            filename=filename,
            original_filename=original_filename,
            status=Status.UPLOADED,
            printer=request.form.get('printer'),
            color=request.form.get('color'),
            material=request.form.get('material')
        )
        db.session.add(job)
        db.session.commit()
        
        # Save file
        if not FileService.save_uploaded_file(file, Status.UPLOADED, filename):
            db.session.delete(job)
            db.session.commit()
            flash('Error saving file', 'error')
            return redirect(request.url)
            
        # Generate thumbnail
        file_path = FileService.get_upload_path(Status.UPLOADED, filename)
        thumbnail_path = ThumbnailService.generate_thumbnail(str(file_path), job.id)
        if thumbnail_path:
            job.thumbnail_path = thumbnail_path
            db.session.commit()
        
        flash('File uploaded successfully!', 'success')
        return redirect(url_for('main.jobs'))
        
    return render_template('main/upload.html')

@main.route('/jobs')
@login_required
def jobs():
    if current_user.is_staff:
        jobs = Job.query.all()
    else:
        jobs = Job.query.filter_by(user_id=current_user.id).all()
    return render_template('main/jobs.html', jobs=jobs)

@main.route('/job/<int:job_id>')
@login_required
def job_detail(job_id):
    job = Job.query.get_or_404(job_id)
    if not current_user.is_staff and job.user_id != current_user.id:
        abort(403)
    return render_template('main/job_detail.html', job=job)

@main.route('/job/<int:job_id>/file')
@login_required
def download_file(job_id):
    job = Job.query.get_or_404(job_id)
    if not current_user.is_staff and job.user_id != current_user.id:
        abort(403)
    file_path = FileService.get_upload_path(job.status, job.filename)
    if not file_path.exists():
        abort(404)
    return send_file(
        str(file_path),
        as_attachment=True,
        download_name=job.original_filename,
        mimetype=FileService.get_mime_type(job.original_filename)
    )

@main.route('/job/<int:job_id>/approve', methods=['POST'])
@login_required
def approve_job(job_id):
    if not current_user.is_staff:
        abort(403)
    
    job = Job.query.get_or_404(job_id)
    if job.status != Status.UPLOADED:
        flash('Job is not in uploaded state', 'error')
        return redirect(url_for('main.jobs'))
    
    # Update job details
    job.weight = float(request.form.get('weight', 0))
    job.time_hours = int(request.form.get('time_hours', 0))
    job.time_minutes = int(request.form.get('time_minutes', 0))
    job.printer = request.form.get('printer')
    
    # Calculate cost
    if job.printer and 'formlabs' in job.printer.lower():
        job.cost = job.weight * 0.20  # $0.20 per gram for Formlabs
    else:
        job.cost = job.weight * 0.10  # $0.10 per gram for other printers
    
    # Move file to pending
    if not FileService.move_file(job.filename, Status.UPLOADED, Status.PENDING):
        flash('Error moving file', 'error')
        return redirect(url_for('main.jobs'))
    
    job.status = Status.PENDING
    db.session.commit()
    
    # Send email to user
    user = User.query.get(job.user_id)
    if user and user.email:
        confirm_url = url_for('main.confirm_job', job_id=job.id, _external=True)
        EmailService.send_job_approval_email(
            user.email,
            job.original_filename,
            job.cost,
            job.time_hours,
            job.time_minutes,
            job.color,
            job.material,
            confirm_url
        )
    
    flash('Job approved and user notified', 'success')
    return redirect(url_for('main.jobs'))

@main.route('/job/<int:job_id>/reject', methods=['POST'])
@login_required
def reject_job(job_id):
    if not current_user.is_staff:
        abort(403)
    
    job = Job.query.get_or_404(job_id)
    if job.status != Status.UPLOADED:
        flash('Job is not in uploaded state', 'error')
        return redirect(url_for('main.jobs'))
    
    reasons = request.form.getlist('reasons')
    job.rejection_reasons = '; '.join(reasons)
    
    # Move file to rejected
    if not FileService.move_file(job.filename, Status.UPLOADED, Status.REJECTED):
        flash('Error moving file', 'error')
        return redirect(url_for('main.jobs'))
    
    job.status = Status.REJECTED
    db.session.commit()
    
    # Send email to user
    user = User.query.get(job.user_id)
    if user and user.email:
        EmailService.send_job_rejection_email(user.email, job.original_filename, reasons)
    
    flash('Job rejected and user notified', 'success')
    return jsonify(success=True)

@main.route('/job/<int:job_id>/confirm', methods=['GET', 'POST'])
@login_required
def confirm_job(job_id):
    job = Job.query.get_or_404(job_id)
    if job.user_id != current_user.id:
        abort(403)
    
    if job.status != Status.PENDING:
        flash('Job is not pending confirmation', 'error')
        return redirect(url_for('main.jobs'))
    
    if request.method == 'POST':
        # Move file to ready_to_print
        if not FileService.move_file(job.filename, Status.PENDING, Status.READY_TO_PRINT):
            flash('Error moving file', 'error')
            return redirect(url_for('main.jobs'))
        
        job.status = Status.READY_TO_PRINT
        job.student_confirmed = True
        db.session.commit()
        
        flash('Print job confirmed', 'success')
        return redirect(url_for('main.jobs'))
    
    return render_template('main/confirm_job.html', job=job)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS'] 