from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, send_from_directory
)
import os, uuid, json
from datetime import datetime
from email_util import send_email

app = Flask(__name__)
app.secret_key = os.urandom(24)

# EXACT on-disk folder names
FOLDERS = {
    'Uploaded':       'Uploaded',
    'Rejected':       'Rejected',
    'ReadytoPrint':   'ReadytoPrint',
    'Printing':       'Printing',
    'Completed':      'Completed',
    'PaidPickedUp':   'PaidPickedUp'
}

ALLOWED_EXT = {'.3mf','.stl','.obj','.form','.idea'}

def allowed_file(filename):
    return os.path.splitext(filename)[1].lower() in ALLOWED_EXT

def save_metadata(folder, filename, data):
    base = os.path.splitext(filename)[0]
    path = os.path.join(folder, f"{base}.json")
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)

def load_metadata(folder, filename):
    base = os.path.splitext(filename)[0]
    path = os.path.join(folder, f"{base}.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return {}

@app.route('/')
def home():
    return redirect(url_for('submit'))

@app.route('/submit', methods=['GET','POST'])
def submit():
    if request.method == 'POST':
        f = request.files.get('file')
        if not f or f.filename == '' or not allowed_file(f.filename):
            flash("Please upload a valid .3mf/.stl/.obj/.form/.idea file", "error")
            return redirect(url_for('submit'))

        uid      = uuid.uuid4().hex[:6]
        date_str = datetime.now().strftime("%Y%m%d")
        ext      = os.path.splitext(f.filename)[1]
        safe_base= request.form['name'].strip().replace(' ','_')
        filename = f"{safe_base}_{date_str}_{uid}{ext}"

        up_folder = FOLDERS['Uploaded']
        f.save(os.path.join(up_folder, filename))

        meta = {
          'name':         request.form.get('name','').strip(),
          'email':        request.form.get('email','').strip(),
          'discipline':   request.form.get('discipline','').strip(),
          'course':       request.form.get('course','').strip(),
          'print_method': request.form.get('print_method','').strip(),
          'print_color':  request.form.get('print_color','').strip(),
          'scaled':       request.form.get('scaled','').strip(),
          'simplified':   request.form.get('simplified','').strip(),
          'overhangs':    request.form.get('overhangs','').strip(),
          'file_type':    request.form.get('filetype','').strip(),
          'minimum_ok':   request.form.get('minimum_ok','').strip(),
          'status':       'Uploaded',
          'submitted':    datetime.now().isoformat()
        }
        save_metadata(up_folder, filename, meta)

        flash("Upload successful! Awaiting slicing and approval.", "success")
        return redirect(url_for('submit'))

    return render_template('upload_form.html')

@app.route('/dashboard')
def dashboard():
    all_files = {}
    for status, folder in FOLDERS.items():
        items = []
        if os.path.isdir(folder):
            for fn in os.listdir(folder):
                if fn.lower().endswith('.json'):
                    continue
                m = load_metadata(folder, fn)
                abs_p = os.path.abspath(os.path.join(folder, fn))
                items.append({
                    'filename': fn,
                    'meta':      m,
                    'path':      os.path.join(folder, fn).replace("\\","/"),
                    'fullpath':  abs_p
                })
        all_files[status] = items
    return render_template('dashboard.html', all_files=all_files)

@app.route('/approve/<filename>', methods=['POST'])
def approve(filename):
    src = FOLDERS['Uploaded']
    base = os.path.splitext(filename)[0]
    meta = load_metadata(src, filename)

    weight = float(request.form.get('weight', 0))
    hours  = float(request.form.get('time',   0))
    meta['weight'] = weight
    meta['time']   = hours
    save_metadata(src, filename, meta)

    confirm_link = url_for('confirm', filename=filename, _external=True)
    subject = "Your 3D Print Job — Please Confirm"
    body = (
      f"Hi {meta['name']},\n\n"
      f"Your uploaded file **{filename}** is ready. Please confirm:\n"
      f"{confirm_link}\n\n"
      "—Digital Fabrication Lab"
    )
    send_email(meta['email'], subject, body)
    flash("Confirmation email sent to student.", "success")
    return redirect(url_for('dashboard'))

@app.route('/reject/<filename>', methods=['POST'])
def reject(filename):
    src = FOLDERS['Uploaded']
    meta = load_metadata(src, filename)

    reasons = request.form.getlist('reasons')
    meta['rejection_reasons'] = reasons
    save_metadata(src, filename, meta)

    subject = "Your 3D Print Request – Rejected"
    reason_text = "\n".join(f"- {r}" for r in reasons)
    body = (
      f"Hi {meta['name']},\n\n"
      f"Cannot print **{filename}** for these reasons:\n{reason_text}\n\n"
      "Please revise and resubmit.\n—Digital Fabrication Lab"
    )
    send_email(meta['email'], subject, body)
    flash("Rejection email sent to student.", "success")
    return redirect(url_for('dashboard'))

@app.route('/confirm/<filename>', methods=['GET','POST'])
def confirm(filename):
    src = FOLDERS['Uploaded']
    dst = FOLDERS['ReadytoPrint']
    if request.method == 'POST':
        choice = request.form['choice']
        if choice == 'yes':
            # move file + JSON
            os.replace(os.path.join(src, filename),
                       os.path.join(dst, filename))
            os.replace(os.path.join(src, f"{os.path.splitext(filename)[0]}.json"),
                       os.path.join(dst, f"{os.path.splitext(filename)[0]}.json"))
            flash(f"{filename} moved to Ready to Print.", "success")
        else:
            flash(f"{filename} remains in Uploaded.", "info")
        return redirect(url_for('dashboard'))

    return render_template('confirm.html', filename=filename)

@app.route('/view/<path:filepath>')
def view(filepath):
    folder, fn = os.path.split(filepath)
    return send_from_directory(folder, fn, as_attachment=False)

if __name__ == '__main__':
    for fld in FOLDERS.values():
        os.makedirs(fld, exist_ok=True)
    app.run(debug=True)
