import os
import re
from flask import Blueprint, render_template, request
from models import Job
from extensions import db
from config import Config

submit_bp = Blueprint('submit', __name__)

def sanitize_filename_component(s):
    return re.sub(r'[^A-Za-z0-9]+', '', s or '')

@submit_bp.route('/submit', methods=['GET', 'POST'])
def submit():
    if request.method == 'POST':
        uploaded = request.files.get('file')
        if not uploaded:
            return render_template('upload_form.html', error='No file uploaded.')

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

        uploaded.save(dest)
        # Render a simple confirmation page for the student
        return render_template('confirmation/submission_success.html', job=job)
    return render_template('upload_form.html') 