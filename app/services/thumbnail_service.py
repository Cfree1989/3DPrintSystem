import os
import trimesh
import pyrender
import numpy as np
from PIL import Image
from flask import current_app
from app.models.job import Status

class ThumbnailService:
    """Service for generating thumbnails of 3D models."""
    
    @staticmethod
    def generate_thumbnail(job):
        """Generate a thumbnail image for a 3D model file.
        
        Args:
            job: Job model instance
            
        Returns:
            str: Path to the generated thumbnail file, or None if generation failed
        """
        try:
            # Get file path
            file_path = os.path.join(
                current_app.config['JOBS_ROOT'],
                Status.UPLOADED.value,
                job.filename
            )
            
            # Skip thumbnail generation in test environment
            if current_app.config.get('TESTING'):
                return None
                
            # Load the mesh
            mesh = trimesh.load(file_path, force='mesh')
            
            # Center the mesh
            mesh.apply_translation(-mesh.bounds.mean(axis=0))
            
            # Scale to fit in a unit cube
            scale = 1.0 / mesh.extents.max()
            mesh.apply_scale(scale)
            
            # Create a scene and add the mesh
            scene = pyrender.Scene()
            scene.add(pyrender.Mesh.from_trimesh(mesh))
            
            # Add a camera
            camera = pyrender.PerspectiveCamera(yfov=np.pi / 3.0)
            scene.add(camera, pose=np.array([
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 1.0, 0.0, 0.0],
                [0.0, 0.0, 1.0, 2.5],
                [0.0, 0.0, 0.0, 1.0]
            ]))
            
            # Add lighting
            light = pyrender.DirectionalLight(color=np.ones(3), intensity=2.0)
            scene.add(light, pose=np.array([
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 1.0, 0.0, 0.0],
                [0.0, 0.0, 1.0, 0.0],
                [0.0, 0.0, 0.0, 1.0]
            ]))
            
            # Render
            r = pyrender.OffscreenRenderer(400, 400)
            color, _ = r.render(scene)
            r.delete()
            
            # Convert to PIL Image and save
            image = Image.fromarray(color)
            
            # Create thumbnails directory if it doesn't exist
            thumbnails_dir = os.path.join(current_app.config['JOBS_ROOT'], 'thumbnails')
            os.makedirs(thumbnails_dir, exist_ok=True)
            
            # Save thumbnail
            thumbnail_path = os.path.join('thumbnails', f'{job.filename}.png')
            image.save(os.path.join(current_app.config['JOBS_ROOT'], thumbnail_path))
            
            return thumbnail_path
            
        except Exception as e:
            current_app.logger.error(f"Thumbnail generation failed for job {job.id} ({job.filename}): {str(e)}")
            return None 