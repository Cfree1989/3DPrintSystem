from flask import current_app, url_for
from flask_mail import Message
from app import mail

class MailService:
    """Service for sending email notifications."""
    
    @staticmethod
    def send_confirmation_email(job):
        """Send a confirmation email for a new job submission.
        
        Args:
            job: Job model instance
        """
        token_url = url_for(
            'main.confirm_job_by_token',
            token=job.confirmation_token,
            _external=True
        )
        
        msg = Message(
            'Confirm Your Print Job',
            sender=current_app.config['MAIL_DEFAULT_SENDER'],
            recipients=[job.student_email]
        )
        
        msg.body = f'''Dear {job.student_name},

Thank you for submitting your 3D print job. Please confirm your submission by clicking the link below:

{token_url}

Your job details:
- File: {job.original_filename}
- Printer: {job.printer}
- Color: {job.color}

This link will expire in 1 hour. After confirming, your job will be reviewed by our staff.

Best regards,
3D Print Lab Team'''
        
        mail.send(msg)
    
    @staticmethod
    def send_approval_email(job):
        """Send an email when a job is approved.
        
        Args:
            job: Job model instance
        """
        msg = Message(
            'Your Print Job Has Been Approved',
            sender=current_app.config['MAIL_DEFAULT_SENDER'],
            recipients=[job.student_email]
        )
        
        msg.body = f'''Dear {job.student_name},

Your 3D print job has been approved! Here are the details:

- File: {job.original_filename}
- Printer: {job.printer}
- Color: {job.color}
- Weight: {job.weight_g}g
- Print Time: {job.time_min} minutes
- Cost: ${job.cost_usd:.2f}

Your job has been added to our print queue. We will notify you when it's ready for pickup.

Best regards,
3D Print Lab Team'''
        
        mail.send(msg)
    
    @staticmethod
    def send_rejection_email(job):
        """Send an email when a job is rejected.
        
        Args:
            job: Job model instance
        """
        reasons = '\n'.join(f'- {reason}' for reason in job.reject_reasons)
        
        msg = Message(
            'Your Print Job Has Been Rejected',
            sender=current_app.config['MAIL_DEFAULT_SENDER'],
            recipients=[job.student_email]
        )
        
        msg.body = f'''Dear {job.student_name},

Unfortunately, your 3D print job has been rejected for the following reasons:

{reasons}

Job details:
- File: {job.original_filename}
- Printer: {job.printer}
- Color: {job.color}

Please make the necessary adjustments and submit a new job.

Best regards,
3D Print Lab Team'''
        
        mail.send(msg) 