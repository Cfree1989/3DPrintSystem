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
    def send_job_approval_email(
        recipient: str,
        filename: str,
        cost: float,
        hours: int,
        minutes: int,
        color: str,
        material: str,
        confirm_url: str
    ):
        """Send job approval notification email."""
        subject = "3D Print Job Approved - Action Required"
        
        # Format time string
        time_str = ""
        if hours > 0:
            time_str += f"{hours} hour{'s' if hours != 1 else ''}"
        if minutes > 0:
            if time_str:
                time_str += " and "
            time_str += f"{minutes} minute{'s' if minutes != 1 else ''}"
        
        body = f"""Your 3D print job for {filename} has been approved!

Details:
- Estimated Cost: ${cost:.2f}
- Print Time: {time_str}
- Color: {color or 'N/A'}
- Material: {material or 'N/A'}

Please confirm your print job by clicking the following link:
{confirm_url}

Note: Your print will not begin until you confirm. The job will be cancelled if not confirmed within 48 hours.

Thank you for using our 3D printing service!"""
        
        html = f"""
        <h2>Your 3D print job for {filename} has been approved!</h2>
        
        <h3>Print Details:</h3>
        <ul>
            <li><strong>Estimated Cost:</strong> ${cost:.2f}</li>
            <li><strong>Print Time:</strong> {time_str}</li>
            <li><strong>Color:</strong> {color or 'N/A'}</li>
            <li><strong>Material:</strong> {material or 'N/A'}</li>
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
        
        <p><em>Note: Your print will not begin until you confirm. The job will be cancelled if not confirmed within 48 hours.</em></p>
        
        <p>Thank you for using our 3D printing service!</p>
        """
        
        return EmailService.send_email(subject, recipient, body, html)
    
    @staticmethod
    def send_job_rejection_email(recipient: str, filename: str, reasons: List[str]):
        """Send job rejection notification email."""
        subject = "3D Print Job Rejected"
        
        reasons_list = "\n".join(f"- {reason}" for reason in reasons)
        
        body = f"""Unfortunately, your 3D print job for {filename} has been rejected.

Rejection Reasons:
{reasons_list}

Please review the reasons and make any necessary adjustments before submitting a new print job.

If you have any questions, please contact the lab staff.

Thank you for your understanding."""
        
        html = f"""
        <h2>3D Print Job Rejected</h2>
        
        <p>Unfortunately, your 3D print job for <strong>{filename}</strong> has been rejected.</p>
        
        <h3>Rejection Reasons:</h3>
        <ul>
            {"".join(f"<li>{reason}</li>" for reason in reasons)}
        </ul>
        
        <p>Please review the reasons and make any necessary adjustments before submitting a new print job.</p>
        
        <p>If you have any questions, please contact the lab staff.</p>
        
        <p>Thank you for your understanding.</p>
        """
        
        return EmailService.send_email(subject, recipient, body, html)
    
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