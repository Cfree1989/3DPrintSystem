from flask import current_app
from itsdangerous import URLSafeTimedSerializer, SignatureExpired, BadSignature

class TokenService:
    """Service for generating and verifying tokens."""
    
    SALT = 'student-job-confirmation'
    DEFAULT_EXPIRY = 7 * 24 * 3600  # 7 days in seconds
    
    @staticmethod
    def generate_token(job):
        """Generate a secure token for job confirmation."""
        serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        return serializer.dumps(job.id, salt=TokenService.SALT)
    
    @staticmethod
    def verify_token(token, expiration=None):
        """Verify a job confirmation token.
        
        Args:
            token (str): The token to verify
            expiration (int): Token expiration time in seconds (default: 7 days)
            
        Returns:
            tuple: (job_id, error_message)
                - If valid: (job_id, None)
                - If invalid: (None, error_message)
        """
        if expiration is None:
            expiration = TokenService.DEFAULT_EXPIRY
            
        serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        try:
            job_id = serializer.loads(
                token,
                salt=TokenService.SALT,
                max_age=expiration
            )
            return job_id, None
        except SignatureExpired:
            return None, "The confirmation link has expired."
        except BadSignature:
            return None, "Invalid confirmation link."
        except Exception as e:
            current_app.logger.error(f"Error verifying token: {str(e)}")
            return None, "An error occurred while processing your request." 