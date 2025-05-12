import os
import numpy as np
import trimesh
import pyrender
from PIL import Image
from flask import current_app
from pathlib import Path

class ThumbnailService:
    """Service for generating thumbnails from 3D model files."""
    
    SUPPORTED_EXTENSIONS = {'.stl', '.obj', '.3mf'}
    
    @staticmethod
    def generate_thumbnail(file_path: str, job_id: int) -> str:
        """Generate a thumbnail for a 3D model file.
        
        Args:
            file_path: Path to the 3D model file
            job_id: ID of the job for naming the thumbnail
            
        Returns:
            Relative path to the thumbnail file, or None if generation failed
        """
        try:
            ext = Path(file_path).suffix.lower()
            if ext not in ThumbnailService.SUPPORTED_EXTENSIONS:
                return None
                
            mesh = trimesh.load(file_path, force='mesh')
            
            # Center the mesh at the origin
            mesh.apply_translation(-mesh.bounds.mean(axis=0))
            
            # Calculate camera distance based on mesh size
            distance = mesh.extents.max() * 1.8
            if distance < 1e-5:  # Handle tiny or flat meshes
                distance = 2.0
                
            # Set up camera transform
            camera_transform = trimesh.scene.cameras.look_at(
                mesh.bounds,
                fov=np.deg2rad(60),
                distance=distance,
                center=mesh.bounds.mean(axis=0)
            )
            
            # Create scene with ambient lighting
            scene = pyrender.Scene(
                ambient_light=np.array([0.1, 0.1, 0.1, 1.0]),
                bg_color=[0.1, 0.1, 0.3, 1.0]
            )
            
            # Add mesh to scene
            scene.add(pyrender.Mesh.from_trimesh(mesh, smooth=False))
            
            # Add camera
            camera = pyrender.PerspectiveCamera(yfov=np.deg2rad(60), aspectRatio=1.0)
            scene.add(camera, pose=camera_transform)
            
            # Add directional light
            light_pose = camera_transform @ np.array([
                [1, 0, 0, 0.5],   # Right of camera
                [0, 1, 0, 0.5],   # Above camera
                [0, 0, 1, 2.0],   # In front of camera
                [0, 0, 0, 1.0]
            ])
            light = pyrender.DirectionalLight(color=np.ones(3), intensity=3.0)
            scene.add(light, pose=light_pose)
            
            # Render thumbnail
            renderer = pyrender.OffscreenRenderer(256, 256)
            try:
                color, _ = renderer.render(scene)
                thumb_img = Image.fromarray(color)
                
                # Save thumbnail
                thumbnails_dir = Path(current_app.root_path) / 'static' / 'thumbnails'
                thumbnails_dir.mkdir(parents=True, exist_ok=True)
                
                thumbnail_filename = f"{job_id}.png"
                thumbnail_path = thumbnails_dir / thumbnail_filename
                thumb_img.save(str(thumbnail_path))
                
                # Return relative path for database storage
                return f"static/thumbnails/{thumbnail_filename}"
            finally:
                renderer.delete()
                
        except Exception as e:
            current_app.logger.error(
                f"Thumbnail generation failed for job {job_id} "
                f"({Path(file_path).name}): {str(e)}",
                exc_info=True
            )
            return None 