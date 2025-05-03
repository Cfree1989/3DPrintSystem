import os
import uuid
from datetime import datetime
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, send_from_directory
)
from flask_sqlalchemy import SQLAlchemy
from filelock import FileLock
from email_util import send_email  # If still used, otherwise remove

# Flask app and config
app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///jobs.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Folder configuration
FOLDERS = {
    'Uploaded': 'Uploaded',
    'Rejected': 'Rejected',
    'ReadyToPrint': 'ReadyToPrint',
    'Printing': 'Printing',
    'Completed': 'Completed',
    'PaidPickedUp': 'PaidPickedUp'
}
ALLOWED_EXT = {'.3mf', '.stl', '.obj', '.form', '.idea'}

# Model
class PrintJob(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String, unique=True, nullable=False)
    name = db.Column(db.String, nullable=False)
    email = db.Column(db.String, nullable=False)
    discipline = db.Column(db.String)
    course = db.Column(db.String)
    print_method = db.Column(db.String)
    print_color = db.Column(db.String)
    scaled = db.Column(db.String)
    simplified = db.Column(db.String)
    overhangs = db.Column(db.String)
    file_type = db.Column(db.String)
    minimum_ok = db.Column(db.String)
    status = db.Column(db.String, nullable=False, default='Uploaded')
    weight = db.Column(db.Float)
    time = db.Column(db.Float)
    rejection_reasons = db.Column(db.String)  # comma-separated
    submitted = db.Column(db.DateTime, default=datetime.utcnow)

# Helpers

def allowed_file(filename):
    return os.path.splitext(filename)[1].lower() in ALLOWED_EXT


def get_file_path(status, filename):
    """Return absolute path of a job file."""
    return os.path.abspath(os.path.join(FOLDERS[status], filename))


def move_with_lock(src_path, dst_path):
    """Atomically move a file under a lock."""
    lock = FileLock('jobs.db.lock')
    with lock:
        os.replace(src_path, dst_path)

# Routes

@app.route('/')
def home():
    return redirect(url_for('submit'))

@app.route('/submit', methods=['GET', 'POST'])
def submit():
    if request.method == 'POST':
        f = request.files.get('file')
        if not f or not f.filename or not allowed_file(f.filename):
            flash("Please upload a valid .3mf/.stl/.obj/.form/.idea file", "error")
            return redirect(url_for('submit'))

        # Build filename
        uid = uuid.uuid4().hex[:6]
        date_str = datetime.now().strftime("%Y%m%d")
        ext = os.path.splitext(f.filename)[1]
        safe_base = request.form['name'].strip().replace(' ', '_')
        filename = f"{safe_base}_{date_str}_{uid}{ext}"

        # Save file
        os.makedirs(FOLDERS['Uploaded'], exist_ok=True)
        dest = os.path.join(FOLDERS['Uploaded'], filename)
        f.save(dest)

        # Create DB record
        job = PrintJob(
            filename=filename,
            name=request.form.get('name','').strip(),
            email=request.form.get('email','').strip(),
            discipline=request.form.get('discipline','').strip(),
            course=request.form.get('course','').strip(),
            print_method=request.form.get('print_method','').strip(),
            print_color=request.form.get('print_color','').strip(),
            scaled=request.form.get('scaled','').strip(),
            simplified=request.form.get('simplified','').strip(),
            overhangs=request.form.get('overhangs','').strip(),
            file_type=request.form.get('filetype','').strip(),
            minimum_ok=request.form.get('minimum_ok','').strip()
        )
        db.session.add(job)
        db.session.commit()

        flash("Upload successful!", "success")
        return redirect(url_for('submit'))

    return render_template('upload_form.html')

@app.route('/dashboard')
def dashboard():
    all_files = {}
    for status in FOLDERS:
        jobs = PrintJob.query.filter_by(status=status).all()
        items = []
        for job in jobs:
            weight = job.weight or 0
            rate = 0.20 if job.print_method == 'Resin' else 0.10
            cost = f"{weight * rate:.2f}"
            items.append({
                'filename': job.filename,
                'meta': {
                    'name': job.name,
                    'email': job.email,
                    'print_color': job.print_color,
                    'print_method': job.print_method,
                    'weight': weight,
                    'time': job.time or 0,
                },
                'fullpath': get_file_path(status, job.filename),
                'cost': cost
            })
        all_files[status] = items

    return render_template('dashboard.html', all_files=all_files)

@app.route('/approve/<filename>', methods=['POST'])
def approve(filename):
    job = PrintJob.query.filter_by(filename=filename, status='Uploaded').first_or_404()
    # Parse inputs
    job.weight = float(request.form.get('weight', 0))
    job.time = float(request.form.get('time', 0))
    job.status = 'ReadyToPrint'

    # Move file on disk
    src = get_file_path('Uploaded', filename)
    dst = os.path.join(FOLDERS['ReadyToPrint'], filename)
    os.makedirs(FOLDERS['ReadyToPrint'], exist_ok=True)
    move_with_lock(src, dst)

    db.session.commit()
    flash(f"{filename} approved and moved to ReadyToPrint.", "success")
    return redirect(url_for('dashboard'))

@app.route('/reject/<filename>', methods=['POST'])
def reject(filename):
    job = PrintJob.query.filter_by(filename=filename, status='Uploaded').first_or_404()
    reasons = request.form.getlist('reasons')
    job.rejection_reasons = ','.join(reasons)
    job.status = 'Rejected'

    # Move file
    src = get_file_path('Uploaded', filename)
    dst = os.path.join(FOLDERS['Rejected'], filename)
    os.makedirs(FOLDERS['Rejected'], exist_ok=True)
    move_with_lock(src, dst)

    db.session.commit()
    flash(f"{filename} rejected.", "info")
    return redirect(url_for('dashboard'))

@app.route('/view/<path:filepath>')
def view(filepath):
    folder, fn = os.path.split(filepath)
    return send_from_directory(folder, fn, as_attachment=False)

# Initialize DB and folders
with app.app_context():
    db.create_all()
    for fld in FOLDERS.values():
        os.makedirs(fld, exist_ok=True)

if __name__ == '__main__':
    from waitress import serve
    serve(app, host='0.0.0.0', port=5000)
