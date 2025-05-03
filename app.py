import os
import uuid
from datetime import datetime
from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, send_from_directory, abort
)
from flask_sqlalchemy import SQLAlchemy
from filelock import FileLock
from email_util import send_email   # loads .env via python-dotenv

# ——— Flask & Database Setup —————————————————————————————————————————————
app = Flask(__name__)
app.secret_key = os.urandom(24)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///jobs.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# ——— Folder & File Configuration —————————————————————————————————————
FOLDERS = {
    'Uploaded':      'Uploaded',
    'Rejected':      'Rejected',
    'ReadyToPrint':  'ReadyToPrint',
    'Printing':      'Printing',
    'Completed':     'Completed',
    'PaidPickedUp':  'PaidPickedUp',
}
ALLOWED_EXT = {'.3mf', '.stl', '.obj', '.form', '.idea'}

def allowed_file(filename):
    return os.path.splitext(filename)[1].lower() in ALLOWED_EXT

def get_file_path(status, filename):
    return os.path.abspath(os.path.join(FOLDERS[status], filename))

def move_with_lock(src_path, dst_path):
    lock = FileLock('jobs.db.lock')
    with lock:
        os.replace(src_path, dst_path)

# ——— Model Definition ——————————————————————————————————————————————————
class PrintJob(db.Model):
    id                = db.Column(db.Integer, primary_key=True)
    filename          = db.Column(db.String, unique=True, nullable=False)
    name              = db.Column(db.String, nullable=False)
    email             = db.Column(db.String, nullable=False)
    discipline        = db.Column(db.String)
    course            = db.Column(db.String)
    print_method      = db.Column(db.String)
    print_color       = db.Column(db.String)
    scaled            = db.Column(db.String)
    simplified        = db.Column(db.String)
    overhangs         = db.Column(db.String)
    file_type         = db.Column(db.String)
    minimum_ok        = db.Column(db.String)
    status            = db.Column(db.String, nullable=False, default='Uploaded')
    weight            = db.Column(db.Float)
    time              = db.Column(db.Float)
    rejection_reasons = db.Column(db.String)    # comma-separated
    submitted         = db.Column(db.DateTime, default=datetime.utcnow)

# ——— Routes ———————————————————————————————————————————————————————

@app.route('/')
def home():
    return redirect(url_for('submit'))

@app.route('/submit', methods=['GET','POST'])
def submit():
    if request.method == 'POST':
        f = request.files.get('file')
        if not f or not f.filename or not allowed_file(f.filename):
            flash("Please upload a valid .3mf/.stl/.obj/.form/.idea file", "error")
            return redirect(url_for('submit'))

        # Build safe filename
        uid       = uuid.uuid4().hex[:6]
        date_str  = datetime.now().strftime("%Y%m%d")
        ext       = os.path.splitext(f.filename)[1]
        safe_base = request.form['name'].strip().replace(' ','_')
        filename  = f"{safe_base}_{date_str}_{uid}{ext}"

        # Save file to Uploaded
        os.makedirs(FOLDERS['Uploaded'], exist_ok=True)
        dest = os.path.join(FOLDERS['Uploaded'], filename)
        f.save(dest)

        # Create database record
        job = PrintJob(
            filename     = filename,
            name         = request.form.get('name','').strip(),
            email        = request.form.get('email','').strip(),
            discipline   = request.form.get('discipline','').strip(),
            course       = request.form.get('course','').strip(),
            print_method = request.form.get('print_method','').strip(),
            print_color  = request.form.get('print_color','').strip(),
            scaled       = request.form.get('scaled','').strip(),
            simplified   = request.form.get('simplified','').strip(),
            overhangs    = request.form.get('overhangs','').strip(),
            file_type    = request.form.get('filetype','').strip(),
            minimum_ok   = request.form.get('minimum_ok','').strip()
        )
        db.session.add(job)
        db.session.commit()

        flash("Upload successful! Awaiting confirmation.", "success")
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
            rate   = 0.20 if job.print_method=='Resin' else 0.10
            cost   = f"{weight * rate:.2f}"

            items.append({
                'job_id':   job.id,
                'filename': job.filename,
                'fullpath': get_file_path(status, job.filename),
                'cost':     cost,
                'meta': {
                    'name':          job.name,
                    'email':         job.email,
                    'print_color':   job.print_color,
                    'print_method':  job.print_method,
                    'weight':        weight,
                    'time':          job.time or 0,
                }
            })
        all_files[status] = items

    return render_template('dashboard.html', all_files=all_files)


@app.route('/approve/<int:job_id>', methods=['POST'])
def approve(job_id):
    job = PrintJob.query.get_or_404(job_id)
    job.weight = float(request.form['weight'])
    job.time   = float(request.form['time'])
    db.session.commit()

    # Send confirmation email
    confirm_link = url_for('confirm', job_id=job.id, _external=True)
    subject      = "Your 3D Print Job — Please Confirm"
    body         = (
        f"Hi {job.name},\n\n"
        f"Your file **{job.filename}** is ready. Please confirm here:\n{confirm_link}\n\n"
        "—Digital Fabrication Lab"
    )
    send_email(job.email, subject, body)

    flash("Confirmation email sent to student.", "success")
    return redirect(url_for('dashboard'))


@app.route('/confirm/<int:job_id>', methods=['GET','POST'])
def confirm(job_id):
    job = PrintJob.query.get_or_404(job_id)
    if request.method=='POST' and request.form.get('choice')=='yes':
        # Move file on disk
        src = os.path.join(FOLDERS['Uploaded'], job.filename)
        dst = os.path.join(FOLDERS['ReadyToPrint'], job.filename)
        move_with_lock(src, dst)

        # Update status
        job.status = 'ReadyToPrint'
        db.session.commit()

        flash(f"{job.filename} moved to Ready to Print.", "success")
        return redirect(url_for('dashboard'))

    return render_template('confirm.html', filename=job.filename)


@app.route('/reject/<int:job_id>', methods=['POST'])
def reject(job_id):
    job     = PrintJob.query.get_or_404(job_id)
    reasons = request.form.getlist('reasons')
    job.rejection_reasons = ",".join(reasons)
    job.status            = 'Rejected'
    db.session.commit()

    # Send rejection email
    subject = "Your 3D Print Request – Rejected"
    body    = f"Hi {job.name},\n\nReasons:\n" + "\n".join(f"- {r}" for r in reasons)
    send_email(job.email, subject, body)

    # Move file on disk
    src = os.path.join(FOLDERS['Uploaded'], job.filename)
    dst = os.path.join(FOLDERS['Rejected'], job.filename)
    move_with_lock(src, dst)

    flash("Rejection email sent and file moved.", "success")
    return redirect(url_for('dashboard'))


@app.route('/view/<path:filepath>')
def view(filepath):
    folder, fn = os.path.split(filepath)
    if not os.path.isfile(os.path.join(folder, fn)):
        abort(404)
    return send_from_directory(folder, fn, as_attachment=False)


# ——— Initialization —————————————————————————————————————————————————
with app.app_context():
    db.create_all()
    for fld in FOLDERS.values():
        os.makedirs(fld, exist_ok=True)


if __name__=='__main__':
    print("▶️  Starting Flask DEBUG server on http://0.0.0.0:5000")
    app.run(debug=True, host='0.0.0.0', port=5000)



