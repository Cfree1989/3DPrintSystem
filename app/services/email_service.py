from flask import current_app, render_template
from flask_mail import Mail, Message
from threading import Thread
from app import mail
from typing import List

class EmailService:
    """Service for handling all email notifications in the system."""
    
    @staticmethod
    def send_email(subject: str, recipient: str, body: str, html: str = None):
        """Send an email using Flask-Mail.
        
        Args:
            subject: Email subject
            recipient: Recipient email address
            body: Plain text email body
            html: Optional HTML version of the email body
        """
        try:
            msg = Message(
                subject=subject,
                recipients=[recipient],
                body=body,
                html=html,
                sender=current_app.config['MAIL_DEFAULT_SENDER']
            )
            mail.send(msg)
            return True
        except Exception as e:
            current_app.logger.error(f"Error sending email to {recipient}: {str(e)}")
            return False
    
    @staticmethod
    def send_job_approval_email(student_email: str, filename: str, cost: float, hours: int, minutes: int, material: str, confirm_url: str):
        """Send an approval email for a job.
        
        Args:
            student_email: Recipient email address
            filename: Original filename
            cost: Calculated cost
            hours: Print time hours
            minutes: Print time minutes
            material: Material type
            confirm_url: Confirmation URL
        """
        subject = '3D Print Job Approved - Action Required'
        
        # Plain text version
        body = f'''Your 3D print job has been approved and is ready for confirmation!

File: {filename}
Estimated Cost: ${cost:.2f}
Print Time: {hours}h {minutes}m
Material: {material}

Please confirm your print job by clicking the following link:
{confirm_url}

This link will expire in 7 days. After confirmation, your job will be moved to the print queue.

Best regards,
3D Print Lab Team'''

        # HTML version
        html = f'''
        <h2>Your 3D print job has been approved and is ready for confirmation!</h2>
        
        <h3>Print Details:</h3>
        <ul>
            <li><strong>File:</strong> {filename}</li>
            <li><strong>Estimated Cost:</strong> ${cost:.2f}</li>
            <li><strong>Print Time:</strong> {hours}h {minutes}m</li>
            <li><strong>Material:</strong> {material}</li>
        </ul>
        
        <p>Please confirm your print job by clicking the button below:</p>
        
        <p style="text-align: center;">
            <a href="{confirm_url}" 
               style="background-color: #4CAF50; 
                      color: white; 
                      padding: 14px 25px; 
                      text-decoration: none; 
                      display: inline-block; 
                      border-radius: 4px;">
                Confirm Print Job
            </a>
        </p>
        
        <p><em>This link will expire in 7 days. After confirmation, your job will be moved to the print queue.</em></p>
        
        <p>Best regards,<br>3D Print Lab Team</p>
        '''

        return EmailService.send_email(subject, student_email, body, html)
    
    @staticmethod
    def send_job_rejection_email(student_email: str, filename: str, reasons: list):
        """Send a rejection email for a job.
        
        Args:
            student_email: Recipient email address
            filename: Original filename
            reasons: List of rejection reasons
        """
        subject = '3D Print Job Rejected'
        
        # Format reasons list
        reasons_list = '\n'.join(f'- {reason}' for reason in reasons)
        
        # Plain text version
        body = f'''Your 3D print job has been rejected.

File: {filename}

Reasons for rejection:
{reasons_list}

Please make the necessary adjustments and submit a new print job.

Best regards,
3D Print Lab Team'''

        # HTML version
        html = f'''
        <h2>Your 3D print job has been rejected.</h2>
        
        <p><strong>File:</strong> {filename}</p>
        
        <h3>Reasons for rejection:</h3>
        <ul>
            {''.join(f'<li>{reason}</li>' for reason in reasons)}
        </ul>
        
        <p>Please make the necessary adjustments and submit a new print job.</p>
        
        <p>Best regards,<br>3D Print Lab Team</p>
        '''

        return EmailService.send_email(subject, student_email, body, html)
    
    @staticmethod
    def send_job_complete_email(recipient: str, filename: str, pickup_location: str):
        """Send job completion notification email."""
        subject = "Your 3D Print is Ready for Pickup"
        
        body = f"""Great news! Your 3D print job for {filename} is complete and ready for pickup.

Pickup Location: {pickup_location}

Please bring your student ID and payment when picking up your print.

Thank you for using our 3D printing service!"""
        
        html = f"""
        <h2>Your 3D Print is Ready!</h2>
        
        <p>Great news! Your 3D print job for <strong>{filename}</strong> is complete and ready for pickup.</p>
        
        <h3>Pickup Information:</h3>
        <p><strong>Location:</strong> {pickup_location}</p>
        
        <p><em>Please bring your student ID and payment when picking up your print.</em></p>
        
        <p>Thank you for using our 3D printing service!</p>
        """
        
        return EmailService.send_email(subject, recipient, body, html)

def send_async_email(app, msg):
    with app.app_context():
        mail.send(msg)

def send_email(subject, sender, recipients, text_body, html_body):
    msg = Message(subject, sender=sender, recipients=recipients)
    msg.body = text_body
    msg.html = html_body
    
    # Send email asynchronously
    Thread(target=send_async_email,
           args=(current_app._get_current_object(), msg)).start()

def send_password_reset_email(user):
    token = user.get_reset_password_token()
    send_email(
        '[3D Print System] Reset Your Password',
        sender=current_app.config['MAIL_DEFAULT_SENDER'],
        recipients=[user.email],
        text_body=render_template('email/reset_password.txt',
                                user=user, token=token),
        html_body=render_template('email/reset_password.html',
                                user=user, token=token)
    ) 