from flask import Blueprint, render_template, flash, redirect, url_for, request, current_app, send_file, jsonify, abort, session
from werkzeug.utils import secure_filename
from app.models.job import Job, Status
from extensions import db
from app.services.file_service import FileService
from app.services.thumbnail_service import ThumbnailService
from app.services.email_service import EmailService
from config import Config
import os
from datetime import datetime, timedelta
from pathlib import Path
from functools import wraps
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadTimeSignature
from app.services.token_service import TokenService
from app.services.mail_service import MailService

main = Blueprint('main', __name__)

# Helper to get the token serializer
def get_token_serializer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'])

# Decorator for staff-only routes
def staff_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'is_staff' not in session:
            return redirect(url_for('main.staff_login'))
        return f(*args, **kwargs)
    return decorated_function

@main.route('/')
@main.route('/index')
def index():
    # Redirect root to the submit page
    return redirect(url_for('main.submit'))

@main.route('/dashboard')
@staff_required # Use the new decorator
def dashboard():
    # statuses_from_config = Config.STATUS_FOLDERS # ['Uploaded', 'Pending', ...]
    # The template dashboard.html expects lowercase_with_underscore keys 
    # e.g., 'uploaded', 'pending', 'ready_to_print'
    
    jobs_by_status_for_template = {}
    for db_status_value in Config.STATUS_FOLDERS: # These are the values stored in DB, e.g., "Uploaded", "ReadyToPrint"
        # Convert DB status value to the key format expected by the template
        template_key = db_status_value.lower().replace(' ', '_') # 'Uploaded' -> 'uploaded', 'ReadyToPrint' -> 'readytoprint' - wait, template uses 'ready_to_print'
        
        # Let's be explicit based on the template's hardcoded list:
        # 'uploaded', 'pending', 'rejected', 'ready_to_print', 'printing', 'completed', 'paid_picked_up'
        # The values in Config.STATUS_FOLDERS are 'Uploaded', 'Pending', 'Rejected', 'ReadyToPrint', 'Printing', 'Completed', 'PaidPickedUp'

        # Correct mapping from Config.STATUS_FOLDERS to template keys:
        if db_status_value == Config.UPLOADED_FOLDER: # 'Uploaded'
            template_key = 'uploaded'
        elif db_status_value == Config.PENDING_FOLDER: # 'Pending'
            template_key = 'pending'
        elif db_status_value == Config.REJECTED_FOLDER: # 'Rejected'
            template_key = 'rejected'
        elif db_status_value == Config.READY_TO_PRINT_FOLDER: # 'ReadyToPrint'
            template_key = 'ready_to_print'
        elif db_status_value == Config.PRINTING_FOLDER: # 'Printing'
            template_key = 'printing'
        elif db_status_value == Config.COMPLETED_FOLDER: # 'Completed'
            template_key = 'completed'
        elif db_status_value == Config.PAID_PICKED_UP_FOLDER: # 'PaidPickedUp'
            template_key = 'paid_picked_up'
        else:
            continue # Should not happen if Config.STATUS_FOLDERS is aligned
            
        jobs_by_status_for_template[template_key] = Job.query.filter_by(status=db_status_value).all()

    # Ensure all keys expected by template are present, even if with empty lists
    expected_template_keys = ['uploaded', 'pending', 'rejected', 'ready_to_print', 'printing', 'completed', 'paid_picked_up']
    for key in expected_template_keys:
        if key not in jobs_by_status_for_template:
            jobs_by_status_for_template[key] = []
            
    return render_template('dashboard.html', jobs_by_status=jobs_by_status_for_template)

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
            
        original_filename = file.filename
        filename = FileService.secure_job_filename(
            username=student_name, 
            printer=request.form.get('printer', ''),
            color=request.form.get('color', ''),
            original_filename=original_filename
        )
        
        job = Job(
            student_name=student_name,
            student_email=student_email,
            filename=filename,
            original_filename=original_filename,
            printer=request.form.get('printer'),
            color=request.form.get('color'),
            material=request.form.get('material')
        )
        db.session.add(job)
        try:
            db.session.commit() 
            # job.status is already the string value after commit due to model default handling by SQLAlchemy
            current_app.logger.info(f"Job created successfully in DB. ID: {job.id}, Status: {job.status if hasattr(job, 'status') and job.status else 'N/A'}")
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f'Error during initial job commit or logging: {e}', exc_info=True)
            flash(f'Error creating job record. Please try again.', 'error')
            return redirect(request.url)
            
        if FileService.save_uploaded_file(file, Status.UPLOADED.value, filename):
            current_app.logger.info(f"File saved successfully for job ID: {job.id}. Filename: {filename}")
            
            try:
                file_path = FileService.get_upload_path(Status.UPLOADED.value, filename)
                thumbnail_path = ThumbnailService.generate_thumbnail(str(file_path), job.id)
                if thumbnail_path:
                    job.thumbnail_path = thumbnail_path
                    db.session.commit() 
                    current_app.logger.info(f"Thumbnail path saved for job ID: {job.id}")
                else:
                    current_app.logger.warning(f'Thumbnail generation returned no path for job {job.id}')
            except Exception as thumb_e:
                db.session.rollback() 
                current_app.logger.error(f'Error during thumbnail generation for job {job.id}: {thumb_e}', exc_info=True)
            
            return redirect(url_for('main.submission_confirmed'))

        else: # FileService.save_uploaded_file returned False
            current_app.logger.error(f"FileService.save_uploaded_file returned False for filename: {filename}. Associated job ID was: {job.id}")
            try:
                db.session.delete(job)
                db.session.commit()
                current_app.logger.info(f"Job record {job.id} deleted after file save failure.")
            except Exception as cleanup_e:
                db.session.rollback()
                current_app.logger.error(f'Error cleaning up job record {job.id} after file save failure: {cleanup_e}', exc_info=True)
            flash('Error saving uploaded file. Please try again.', 'error')
            return redirect(request.url)
        
    return render_template('main/submit.html')

@main.route('/submission-confirmed')
def submission_confirmed():
    return render_template('main/submission_confirmed.html', title='Submission Confirmed')

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
@staff_required
def approve_job(job_id):
    """Approve a job and generate confirmation token."""
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
        # Update job status and generate confirmation token
        job.update_status(Status.PENDING)
        token = TokenService.generate_token(job)
        job.confirm_url = url_for('main.confirm_job_by_token', token=token, _external=True)
        db.session.commit()
        
        # Send confirmation email
        if job.student_email:
            try:
                hours = job.time_min // 60
                minutes = job.time_min % 60
                EmailService.send_job_approval_email(
                    student_email=job.student_email,
                    filename=job.original_filename,
                    cost=job.cost,
                    hours=hours,
                    minutes=minutes,
                    material=job.material,
                    confirm_url=job.confirm_url
                )
            except Exception as email_error:
                current_app.logger.error(f'Error sending approval email for job {job.id}: {email_error}')
                flash('Job approved, but there was an error sending the confirmation email.', 'warning')
                return redirect(url_for('main.jobs'))
        
        flash('Job approved and confirmation email sent.', 'success')
        return redirect(url_for('main.jobs'))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error updating job {job.id} status to PENDING: {e}')
        flash(f'Error updating job status: {e}', 'error')
        # Attempt to move file back
        FileService.move_file(job.filename, Status.PENDING, Status.UPLOADED)
        return redirect(url_for('main.jobs'))

@main.route('/job/<int:job_id>/reject', methods=['POST'])
@staff_required
def reject_job(job_id):
    """Reject a job with reasons."""
    job = Job.query.get_or_404(job_id)
    
    # Get reject reasons from form
    reasons = request.form.getlist('reasons')  # Remove [] from key name
    if not reasons:
        return jsonify({'error': 'At least one rejection reason is required'}), 400
    
    try:
        # Update job status and reasons
        job.reject_reasons = reasons
        old_status = job.status
        job.update_status(Status.REJECTED)
        
        # Move file back to rejected directory
        if not FileService.move_file(job.filename, Status(old_status), Status.REJECTED):
            db.session.rollback()
            return jsonify({'error': 'Error moving file to rejected directory'}), 500
        
        # Send rejection email
        if job.student_email:
            try:
                EmailService.send_job_rejection_email(
                    student_email=job.student_email,
                    filename=job.original_filename,
                    reasons=reasons
                )
            except Exception as email_error:
                current_app.logger.error(f'Error sending rejection email for job {job.id}: {email_error}')
                # Don't rollback the rejection just because email failed
        
        db.session.commit()
        return jsonify({'message': 'Job rejected successfully'}), 200
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error rejecting job {job.id}: {e}')
        return jsonify({'error': str(e)}), 500

@main.route('/job/confirm/<token>', methods=['GET', 'POST'])
def confirm_job_by_token(token):
    """Confirm a job using a confirmation token."""
    # Verify the token
    job_id, error = TokenService.verify_token(token)
    if error:
        flash(error, 'error')
        return redirect(url_for('main.submit'))
    
    # Get the job
    job = Job.query.get_or_404(job_id)
    
    # Check job status
    if job.status != Status.PENDING:
        flash("This job must be in 'Pending' status to be confirmed.", 'error')
        return redirect(url_for('main.submit'))
    
    if request.method == 'GET':
        return render_template('student/confirm_job.html', job=job, token=token)
    
    try:
        # Update job status
        job.student_confirmed = True
        job.update_status(Status.CONFIRMED)
        
        # Move file to confirmed directory
        if not FileService.move_file(job.filename, Status.PENDING, Status.CONFIRMED):
            db.session.rollback()
            flash('Error moving file to confirmed directory', 'error')
            return redirect(url_for('main.submit'))
        
        db.session.commit()
        flash('Job confirmed successfully! Your print will begin soon.', 'success')
        return render_template('student/job_confirmed.html', job=job)
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f'Error confirming job {job.id}: {e}')
        flash('An error occurred while confirming your job. Please try again or contact staff.', 'error')
        return redirect(url_for('main.submit'))

# Remove unused allowed_file function
# def allowed_file(filename): ... removed ...

# --- Staff Login/Logout Routes ---
@main.route('/staff/login', methods=['GET', 'POST'])
def staff_login():
    if request.method == 'POST':
        if request.form.get('password') == current_app.config['STAFF_PASSWORD']:
            session['is_staff'] = True
            flash('Successfully logged in as staff.', 'success')
            return redirect(url_for('main.dashboard'))
        flash('Invalid password', 'error')
    return render_template('main/staff_login.html')

@main.route('/staff/logout')
def staff_logout():
    session.pop('is_staff', None)
    flash('You have been logged out.', 'success')
    return redirect(url_for('main.submit')) 