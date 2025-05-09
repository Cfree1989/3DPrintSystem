import os
import re
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from models import Job
from extensions import db
from config import Config
import trimesh
import pyrender
from PIL import Image
import numpy as np

submit_bp = Blueprint('submit', __name__)

def sanitize_filename_component(s):
    return re.sub(r'[^A-Za-z0-9]+', '', s or '')

@submit_bp.route('/submit', methods=['GET', 'POST'])
def submit():
    if request.method == 'POST':
        uploaded = request.files.get('file')
        if not uploaded:
            flash('No file uploaded.', 'error')
            return render_template('upload_form.html')

        # Gather form data
        name = request.form.get('name')
        email = request.form.get('email')
        print_method = request.form.get('print_method')
        color = request.form.get('print_color')

        # Build new filename with numeric descriptor
        name_part = sanitize_filename_component(name.replace(' ', ''))
        method_part = sanitize_filename_component(print_method)
        color_part = sanitize_filename_component(color)
        ext = os.path.splitext(uploaded.filename)[1]
        # Count previous files by this student with same method/color
        base_query = Job.query.filter_by(name=name, printer=print_method, color=color)
        descriptor_num = base_query.count() + 1
        base_filename = f"{name_part}_{method_part}_{color_part}_{descriptor_num}"
        new_filename = base_filename + ext
        dest = os.path.join(Config.JOBS_ROOT, Config.UPLOADED_FOLDER, new_filename)
        # Ensure uniqueness in case of race
        counter = descriptor_num
        while os.path.exists(dest):
            counter += 1
            new_filename = f"{name_part}_{method_part}_{color_part}_{counter}{ext}"
            dest = os.path.join(Config.JOBS_ROOT, Config.UPLOADED_FOLDER, new_filename)

        job = Job(
            filename=new_filename,
            name=name,
            email=email,
            status=Config.UPLOADED_FOLDER,
            printer=print_method,
            color=color
        )
        db.session.add(job)
        db.session.commit()
        current_app.logger.info(f'New job {job.id} ({job.filename}) created successfully for {name} ({email}).')

        uploaded.save(dest)

        # Generate thumbnail for supported 3D files
        thumbnail_path = None
        try:
            if ext.lower() in ['.stl', '.obj', '.3mf']:
                mesh = trimesh.load(dest, force='mesh')

                # Center the mesh at the origin
                mesh.apply_translation(-mesh.bounds.mean(axis=0))

                # Calculate a suitable distance for the camera
                # Use the mesh's maximum extent to ensure the camera is far enough away
                # Add a small buffer (e.g., 1.5x to 2x the max extent)
                distance = mesh.extents.max() * 1.8 # Increased buffer slightly
                if distance < 1e-5: # handle case where mesh is tiny or flat
                    distance = 2.0 # default reasonable distance

                # Get camera transform looking at the mesh bounds from the calculated distance
                camera_transform = trimesh.scene.cameras.look_at(mesh.bounds, fov=np.deg2rad(60), distance=distance, center=mesh.bounds.mean(axis=0))

                pyrender_scene = pyrender.Scene(ambient_light=np.array([0.1, 0.1, 0.1, 1.0]), bg_color=[0.1, 0.1, 0.3, 1.0]) # Slightly darker bg
                pyrender_mesh = pyrender.Mesh.from_trimesh(mesh, smooth=False)
                pyrender_scene.add(pyrender_mesh)
                
                # Add camera to pyrender scene
                pyrender_camera = pyrender.PerspectiveCamera(yfov=np.deg2rad(60), aspectRatio=1.0)
                pyrender_scene.add(pyrender_camera, pose=camera_transform)

                # Add a directional light, relative to the camera's view
                # Simple light: coming from a bit above and to the side of the camera's viewpoint
                light_pose = camera_transform @ np.array([
                    [1, 0, 0, 0.5],  # Offset slightly to the right of camera
                    [0, 1, 0, 0.5],  # Offset slightly above camera
                    [0, 0, 1, 2.0],  # In front of camera
                    [0, 0, 0, 1  ]
                ])
                light = pyrender.DirectionalLight(color=np.ones(3), intensity=3.0)
                pyrender_scene.add(light, pose=light_pose) # Add light with a pose

                # Offscreen rendering
                r = pyrender.OffscreenRenderer(viewport_width=256, viewport_height=256)
                color, _ = r.render(pyrender_scene)
                r.delete() # Important to free GPU resources

                thumb_img = Image.fromarray(color)
                thumbnails_dir = os.path.join(Config.BASE_DIR, 'thumbnails')
                os.makedirs(thumbnails_dir, exist_ok=True)
                thumbnail_filename = f"{job.id}.png"
                thumbnail_path = os.path.join(thumbnails_dir, thumbnail_filename)
                thumb_img.save(thumbnail_path)
                # Store relative path for serving
                job.thumbnail_path = f"thumbnails/{thumbnail_filename}"
                db.session.commit()
                current_app.logger.info(f'Thumbnail generated successfully for job {job.id} at {thumbnail_path}')
        except Exception as e:
            current_app.logger.error(f"Thumbnail generation failed for job {job.id} ({new_filename if 'new_filename' in locals() else 'unknown'}): {e}", exc_info=True)

        flash('File uploaded successfully! You will receive an email when your print is ready for confirmation.', 'success')
        return redirect(url_for('submit.submission_succeeded_page'))
    return render_template('upload_form.html')

@submit_bp.route('/submission-successful')
def submission_succeeded_page():
    return render_template('submission_successful.html') 