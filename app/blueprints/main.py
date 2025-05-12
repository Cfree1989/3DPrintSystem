from flask import Blueprint, render_template, flash, redirect, url_for, request, current_app, send_file, jsonify, abort, session
from werkzeug.utils import secure_filename
from app.models.job import Job, Status
from extensions import db
from app.services.file_service import FileService
from app.services.thumbnail_service import ThumbnailService
from app.services.email_service import EmailService
from config import Config
import os
from datetime import datetime
from pathlib import Path
from functools import wraps

main = Blueprint('main', __name__)

# Decorator for staff-only routes
def staff_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_staff'):
            flash('Staff login required to access this page.', 'warning')
            return redirect(url_for('main.staff_login')) # Redirect to staff login page
        return f(*args, **kwargs)
    return decorated_function

@main.route('/')
@main.route('/index')
# @login_required # Removed
def index():
    # This can be a simple welcome page or redirect to submit/login
    return render_template('main/index.html', title='Home')

@main.route('/dashboard')
@staff_required # Use the new decorator
def dashboard():
    statuses = Config.STATUS_FOLDERS
    jobs_by_status = {status: Job.query.filter_by(status=status).all() for status in statuses}
    return render_template('main/dashboard.html', jobs_by_status=jobs_by_status)

@main.route('/submit', methods=['GET', 'POST'])
# @login_required # Removed - Public access
def submit():
    if request.method == 'POST':
        student_name = request.form.get('student_name')
        student_email = request.form.get('student_email')
        
        if not student_name or not student_email:
            flash('Student name and email are required.', 'error')
            return redirect(request.url)

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
        # Ensure username is derived from form data now
        filename = FileService.secure_job_filename(
            username=student_name, 
            printer=request.form.get('printer', ''),
            color=request.form.get('color', ''),
            original_filename=original_filename
        )
        
        # Create job record
        job = Job(
            student_name=student_name,
            student_email=student_email,
            filename=filename,
            original_filename=original_filename,
            status=Status.UPLOADED,
            printer=request.form.get('printer'),
            color=request.form.get('color'),
            material=request.form.get('material')
        )
        db.session.add(job)
        # Commit earlier to get job.id if needed
        try:
            db.session.commit() 
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Error creating job record: {e}')
            flash(f'Error creating job record. Please try again.', 'error')
            return redirect(request.url)
            
        # Save file
        if not FileService.save_uploaded_file(file, Status.UPLOADED, filename):
            current_app.logger.error(f'Error saving file for job {job.id}')
            # Attempt to clean up the created job record
            try:
                db.session.delete(job)
                db.session.commit()
            except Exception as cleanup_e:
                db.session.rollback()
                current_app.logger.error(f'Error cleaning up job record {job.id} after file save failure: {cleanup_e}')
            flash('Error saving uploaded file. Please try again.', 'error')
            return redirect(request.url)
            
        # Generate thumbnail
        try:
            file_path = FileService.get_upload_path(Status.UPLOADED, filename)
            thumbnail_path = ThumbnailService.generate_thumbnail(str(file_path), job.id)
            if thumbnail_path:
                job.thumbnail_path = thumbnail_path
                db.session.commit() # Commit again to save thumbnail path
            else:
                 current_app.logger.warning(f'Thumbnail generation failed for job {job.id}')
        except Exception as thumb_e:
            db.session.rollback() # Rollback thumbnail path commit if needed
            current_app.logger.error(f'Error during thumbnail generation for job {job.id}: {thumb_e}')
            # Don't fail the whole submission for thumbnail error
            flash('File submitted, but thumbnail could not be generated.', 'warning') 

        flash('File submitted successfully! Staff will review it.', 'success')
        return redirect(url_for('main.index')) # Redirect to home/confirmation page
        
    # Point to the renamed template file
    return render_template('main/submit.html')

@main.route('/jobs')
@staff_required # Use the new decorator
def jobs():
    # Removed staff/student distinction - staff see all jobs
    jobs = Job.query.order_by(Job.created_at.desc()).all()
    return render_template('main/jobs.html', jobs=jobs)

@main.route('/job/<int:job_id>')
@staff_required # Use the new decorator
def job_detail(job_id):
    job = Job.query.get_or_404(job_id)
    # Removed user check
    return render_template('main/job_detail.html', job=job)

@main.route('/job/<int:job_id>/file')
@staff_required # Use the new decorator
def download_file(job_id):
    job = Job.query.get_or_404(job_id)
    # Removed user check
    file_path = FileService.get_upload_path(job.status, job.filename)
    if not file_path.exists():
        flash(f'File not found for job {job_id}.', 'error')
        abort(404) 
    return send_file(
        str(file_path),
        as_attachment=True,
        download_name=job.original_filename,
        mimetype=FileService.get_mime_type(job.original_filename)
    )

@main.route('/job/<int:job_id>/approve', methods=['POST'])
@staff_required # Use the new decorator
def approve_job(job_id):
    job = Job.query.get_or_404(job_id)
    if job.status != Status.UPLOADED:
        flash('Job is not in uploaded state', 'error')
        return redirect(url_for('main.jobs'))
    
    # Update job details
    job.weight_g = float(request.form.get('weight_g', 0))
    job.time_min = int(request.form.get('time_min', 0))
    job.printer = request.form.get('printer')
    job.material = request.form.get('material')
    job.color = request.form.get('color')
    
    try:
        job.calculate_cost()
    except Exception as e:
        current_app.logger.error(f'Error calculating cost for job {job.id}: {e}')
        flash(f'Error calculating cost: {e}', 'error')
        return redirect(url_for('main.job_detail', job_id=job.id))

    # Move file to pending
    if not FileService.move_file(job.filename, Status.UPLOADED, Status.PENDING):
        flash('Error moving file to pending', 'error')
        return redirect(url_for('main.jobs'))
    
    try:
        job.update_status(Status.PENDING) 
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error updating job {job.id} status to PENDING: {e}')
        flash(f'Error updating job status: {e}', 'error')
        FileService.move_file(job.filename, Status.PENDING, Status.UPLOADED) # Attempt rollback move
        return redirect(url_for('main.jobs'))

    if job.student_email:
        try:
            confirm_url = url_for('main.confirm_job', job_id=job.id, _external=True) # Needs token later
            EmailService.send_job_approval_email(
                job.student_email,
                job.original_filename,
                job.cost,
                job.time_min // 60 if job.time_min else 0,
                job.time_min % 60 if job.time_min else 0,
                job.color,
                job.material,
                confirm_url
            )
        except Exception as email_e:
             current_app.logger.error(f'Error sending approval email for job {job.id}: {email_e}')
             flash('Job approved, but failed to send notification email.', 'warning')
    else:
        flash('Job approved, but no student email provided for notification.', 'warning')

    if not current_app.config.get('TESTING'): # Avoid flash message during tests if desired
        flash('Job approved and student notified (if email provided)', 'success')
    return redirect(url_for('main.jobs'))

@main.route('/job/<int:job_id>/reject', methods=['POST'])
@staff_required # Use the new decorator
def reject_job(job_id):
    job = Job.query.get_or_404(job_id)
    if job.status != Status.UPLOADED:
        flash('Job is not in uploaded state', 'error')
        return redirect(url_for('main.jobs'))
    
    reasons = request.form.getlist('reasons')
    job.rejection_reasons = reasons
    
    # Move file to rejected
    if not FileService.move_file(job.filename, Status.UPLOADED, Status.REJECTED):
        flash('Error moving file to rejected', 'error')
        return redirect(url_for('main.jobs'))
    
    try:
        job.update_status(Status.REJECTED)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error updating job {job.id} status to REJECTED: {e}')
        flash(f'Error updating job status: {e}', 'error')
        FileService.move_file(job.filename, Status.REJECTED, Status.UPLOADED) # Attempt rollback move
        return redirect(url_for('main.jobs'))
        
    if job.student_email:
        try:
            EmailService.send_job_rejection_email(job.student_email, job.original_filename, reasons)
        except Exception as email_e:
            current_app.logger.error(f'Error sending rejection email for job {job.id}: {email_e}')
            flash('Job rejected, but failed to send notification email.', 'warning')
    else:
         flash('Job rejected, but no student email provided for notification.', 'warning')

    if not current_app.config.get('TESTING'):
        flash('Job rejected and student notified (if email provided)', 'success')
    return jsonify(success=True)

@main.route('/job/<int:job_id>/confirm', methods=['GET', 'POST'])
# @login_required # Removed - Needs token-based access for student
def confirm_job(job_id):
    # TODO: Implement secure token validation for student confirmation
    job = Job.query.get_or_404(job_id)
    
    if job.status != Status.PENDING:
        flash('Job is not pending confirmation', 'error')
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        # TODO: Add token validation check here
        
        # Move file to ready_to_print
        if not FileService.move_file(job.filename, Status.PENDING, Status.READY_TO_PRINT):
            flash('Error moving file to ready', 'error')
            return redirect(url_for('main.confirm_job', job_id=job_id))
        
        try:
            job.update_status(Status.READY_TO_PRINT)
            job.student_confirmed = True
            db.session.commit()
        except Exception as e:
             db.session.rollback()
             current_app.logger.error(f'Error confirming job {job.id}: {e}')
             flash(f'Error confirming job: {e}', 'error')
             FileService.move_file(job.filename, Status.READY_TO_PRINT, Status.PENDING) # Attempt rollback move
             return redirect(url_for('main.confirm_job', job_id=job_id))

        flash('Print job confirmed by student', 'success')
        return redirect(url_for('main.index')) 
    
    return render_template('main/confirm_job.html', job=job)

# Remove unused allowed_file function
# def allowed_file(filename): ... removed ...

# --- Staff Login/Logout Routes ---
@main.route('/staff/login', methods=['GET', 'POST'])
def staff_login():
    if session.get('is_staff'):
        return redirect(url_for('main.dashboard'))

    if request.method == 'POST':
        password = request.form.get('password')
        staff_password = current_app.config.get('STAFF_PASSWORD')
        
        if not staff_password:
             flash('Staff authentication is not configured.', 'error')
             current_app.logger.error('STAFF_PASSWORD not set in configuration.')
             return render_template('main/staff_login.html')

        # Compare passwords (plain text for now, consider hashing later)
        if password and password == staff_password:
            session['is_staff'] = True
            session.permanent = True # Make session persistent
            flash('Staff login successful!', 'success')
            return redirect(request.args.get('next') or url_for('main.dashboard'))
        else:
            flash('Incorrect staff password.', 'error')
            
    return render_template('main/staff_login.html') # Need to create this template

@main.route('/staff/logout')
def staff_logout():
    session.pop('is_staff', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('main.staff_login')) 