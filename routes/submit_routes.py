import os
import re
from flask import Blueprint, render_template, request, flash, redirect, url_for, current_app
from flask_login import current_user, login_required
from app.models.job import Job, Status
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
@login_required
def submit():
    if request.method == 'POST':
        uploaded = request.files.get('file')
        if not uploaded:
            flash('No file uploaded.', 'error')
            return render_template('main/upload.html')

        # Get form data
        print_method = request.form.get('printer')  # Changed from print_method to printer to match form
        color = request.form.get('color')

        if not print_method or not color:
            flash('Please select both a printer and color.', 'error')
            return render_template('main/upload.html')

        # Build new filename with numeric descriptor
        name_part = sanitize_filename_component(current_user.username)
        method_part = sanitize_filename_component(print_method)
        color_part = sanitize_filename_component(color)
        ext = os.path.splitext(uploaded.filename)[1].lower()  # Ensure lowercase extension

        if ext not in ['.stl', '.obj', '.3mf']:
            flash('Invalid file type. Allowed types are: STL, OBJ, 3MF', 'error')
            return render_template('main/upload.html')

        # Count previous files by this user with same method/color
        descriptor_num = Job.query.filter_by(
            user_id=current_user.id,
            printer=print_method,
            color=color
        ).count() + 1

        # Generate filename and ensure uniqueness
        counter = descriptor_num
        while True:
            new_filename = f"{name_part}_{method_part}_{color_part}_{counter}{ext}"
            dest = os.path.join(Config.JOBS_ROOT, Config.UPLOADED_FOLDER, new_filename)
            if not os.path.exists(dest):
                break
            counter += 1

        # Create upload directory if it doesn't exist
        os.makedirs(os.path.dirname(dest), exist_ok=True)

        try:
            # Create job record
            job = Job(
                user_id=current_user.id,
                filename=new_filename,
                original_filename=uploaded.filename,
                printer=print_method,
                color=color,
                status=Status.UPLOADED  # Ensure we set the status
            )
            db.session.add(job)
            db.session.commit()

            # Save the uploaded file
            uploaded.save(dest)
            current_app.logger.info(f'New job {job.id} ({job.filename}) created successfully for {current_user.username} ({current_user.email}).')

            try:
                # Generate thumbnail
                mesh = trimesh.load(dest)
                # Center the mesh
                mesh.apply_translation(-mesh.bounds.mean(axis=0))
                # Scale to fit in a unit cube
                scale = 1.0 / mesh.extents.max()
                mesh.apply_scale(scale)

                # Create pyrender scene
                pyrender_scene = pyrender.Scene()
                pyrender_mesh = pyrender.Mesh.from_trimesh(mesh)
                pyrender_scene.add(pyrender_mesh)

                # Add camera
                camera = pyrender.PerspectiveCamera(yfov=np.pi / 3.0)
                camera_pose = np.array([
                    [1.0, 0.0, 0.0, 0.0],
                    [0.0, 1.0, 0.0, 0.0],
                    [0.0, 0.0, 1.0, 2.0],
                    [0.0, 0.0, 0.0, 1.0]
                ])
                pyrender_scene.add(camera, pose=camera_pose)

                # Add light
                light_pose = np.array([
                    [1.0, 0.0, 0.0, 1.0],
                    [0.0, 1.0, 0.0, 1.0],
                    [0.0, 0.0, 1.0, 1.0],
                    [0.0, 0.0, 0.0, 1.0]
                ])
                light = pyrender.DirectionalLight(color=np.ones(3), intensity=3.0)
                pyrender_scene.add(light, pose=light_pose)

                # Offscreen rendering
                r = pyrender.OffscreenRenderer(viewport_width=256, viewport_height=256)
                color, _ = r.render(pyrender_scene)
                r.delete()

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
                current_app.logger.error(f"Thumbnail generation failed for job {job.id} ({new_filename}): {e}", exc_info=True)
                # Continue even if thumbnail generation fails

            flash('File uploaded successfully! You will receive an email when your print is ready for confirmation.', 'success')
            return redirect(url_for('submit.submission_succeeded_page'))

        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error creating job: {str(e)}", exc_info=True)
            flash('An error occurred while processing your upload. Please try again.', 'error')
            return render_template('main/upload.html')

    return render_template('main/upload.html')

@submit_bp.route('/submission-successful')
def submission_succeeded_page():
    return render_template('confirmation/submission_success.html') 