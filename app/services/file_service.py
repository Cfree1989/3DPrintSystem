from pathlib import Path
from typing import Optional
from werkzeug.utils import secure_filename
from flask import current_app
import os
import shutil
from datetime import datetime
import mimetypes
from filelock import FileLock
from app.models.job import Job

class FileService:
    """Centralized service for handling file operations in the 3D print system."""
    
    ALLOWED_EXTENSIONS = {'stl', 'obj', '3mf', 'form', 'idea', 'gcode'}
    
    @staticmethod
    def get_upload_path(status: str, filename: str) -> Path:
        """Get the full path for a file in a specific status directory."""
        return Path(current_app.config['JOBS_ROOT']) / status / filename
    
    @staticmethod
    def allowed_file(filename: str) -> bool:
        """Check if a filename has an allowed extension."""
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in FileService.ALLOWED_EXTENSIONS
    
    @staticmethod
    def secure_job_filename(username: str, printer: str, color: str, original_filename: str) -> str:
        """Generate a secure, standardized filename for a job.
        
        Format: Firstlastname_Printmethod_Color_SimpleNumericID.extension
        Example: JohnDoe_Filament_Blue_123.stl
        """
        # Clean and format the name components
        name_part = ''.join(x for x in username.title() if x.isalnum())
        printer_part = ''.join(x for x in printer if x.isalnum())
        color_part = ''.join(x for x in color if x.isalnum())
        
        # Get file extension
        ext = os.path.splitext(original_filename)[1].lower()
        
        # Get the next available job ID
        try:
            last_job = Job.query.order_by(Job.id.desc()).first()
            job_id = (last_job.id + 1) if last_job else 1
        except Exception as e:
            current_app.logger.error(f"Error getting last job ID: {e}")
            job_id = 1
            
        # Generate the filename
        return f"{name_part}_{printer_part}_{color_part}_{job_id}{ext}"
    
    @staticmethod
    def save_uploaded_file(file, status: str, filename: str) -> bool:
        """Save an uploaded file to the appropriate directory."""
        try:
            upload_path = FileService.get_upload_path(status, filename)
            os.makedirs(upload_path.parent, exist_ok=True)
            file.save(str(upload_path))
            return True
        except Exception as e:
            current_app.logger.error(f"Error saving file {filename}: {str(e)}")
            return False
    
    @staticmethod
    def move_file(filename: str, from_status: str, to_status: str) -> bool:
        """Move a file between status directories with locking."""
        try:
            src_path = FileService.get_upload_path(from_status, filename)
            dst_path = FileService.get_upload_path(to_status, filename)
            
            # Create lock file in the destination directory
            lock = FileLock(dst_path.parent / ".queue.lock")
            with lock:
                os.makedirs(dst_path.parent, exist_ok=True)
                shutil.move(str(src_path), str(dst_path))
            return True
        except Exception as e:
            current_app.logger.error(f"Error moving file {filename}: {str(e)}")
            return False
    
    @staticmethod
    def delete_file(status: str, filename: str) -> bool:
        """Delete a file from a status directory."""
        try:
            file_path = FileService.get_upload_path(status, filename)
            if file_path.exists():
                file_path.unlink()
            return True
        except Exception as e:
            current_app.logger.error(f"Error deleting file {filename}: {str(e)}")
            return False
    
    @staticmethod
    def get_file_size(status: str, filename: str) -> Optional[int]:
        """Get the size of a file in bytes."""
        try:
            file_path = FileService.get_upload_path(status, filename)
            return file_path.stat().st_size if file_path.exists() else None
        except Exception as e:
            current_app.logger.error(f"Error getting file size for {filename}: {str(e)}")
            return None
    
    @staticmethod
    def get_mime_type(filename: str) -> str:
        """Get the MIME type of a file."""
        mime_type, _ = mimetypes.guess_type(filename)
        return mime_type or 'application/octet-stream'
    
    @staticmethod
    def cleanup_old_files(status: str, max_age_days: int) -> int:
        """Clean up files older than max_age_days in a status directory."""
        try:
            path = Path(current_app.config['JOBS_ROOT']) / status
            if not path.exists():
                return 0
            
            now = datetime.utcnow()
            count = 0
            
            for file_path in path.glob('*'):
                if file_path.is_file() and not file_path.name.startswith('.'):
                    age = (now - datetime.fromtimestamp(file_path.stat().st_mtime)).days
                    if age > max_age_days:
                        file_path.unlink()
                        count += 1
            
            return count
        except Exception as e:
            current_app.logger.error(f"Error cleaning up old files in {status}: {str(e)}")
            return 0

def atomic_move(src: Path, dst: Path):
    """Move a file atomically using file locking to prevent race conditions.
    
    Args:
        src (Path): Source file path
        dst (Path): Destination file path
    """
    lock = FileLock(str(dst.parent / ".queue.lock"))
    with lock:
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.replace(dst) 