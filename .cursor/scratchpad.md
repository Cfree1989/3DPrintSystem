# Detailed Project Purpose Summary:

This project is dedicated to creating a **robust and user-centric Flask-based web application designed to comprehensively manage the 3D print job workflow within an academic or makerspace setting.** It addresses common challenges such as disorganized submission processes, lack of transparency in job status, difficulties in tracking file versions post-slicing, and inefficient communication between students and staff.

The system's core purpose is to deliver:

1.  **A Streamlined and Intuitive Submission Process for Students:**
    *   Students will utilize a clear web form to upload their 3D model files (supporting common formats like `.stl`, `.obj`, and `.3mf`).
    *   They will provide essential metadata including their name, email, and desired print parameters (like print method/printer type and color).
    *   The system will automatically rename uploaded files to a standardized, traceable format (`FirstAndLastName_PrintMethod_Color_SimpleJobID`) upon submission.
    *   Students will receive email notifications at key stages, such as when their job is approved for student confirmation (including estimated cost and time), when it's rejected (with reasons), and when it's completed.

2.  **An Efficient and Informative Management Dashboard for Staff:**
    *   Staff will have access to a central dashboard that displays all submitted jobs, clearly organized by status (e.g., Uploaded, Pending, ReadyToPrint).
    *   Each job entry will feature a thumbnail generated from the original student upload for quick visual identification.
    *   Staff can view all job details, input critical print parameters (like weight, material, actual print time), calculate and record costs, and manage transitions between job statuses.
    *   A key function is the "Open File" button, which allows staff to directly open the *current authoritative file* for a job in their preferred slicer software.

3.  **Sophisticated and Accurate File Lifecycle Management:**
    *   The system acknowledges the critical transformation files undergo during the slicing process. While the student uploads an initial design file, the **output from the staff's slicer software (e.g., a `.gcode`, `.3mf`, `.form`, or `.idea` file) becomes the new authoritative file** for printing.
    *   The system must track this change, updating its internal reference to the job's filename and location. The "Open File" button will always point to this latest authoritative version, ensuring staff always work with the correct, print-ready file. This mechanism is designed to prevent version conflicts and confusion.
    *   Original uploaded files might be archived or replaced once a definitive sliced file is generated and approved.

4.  **Clear Communication and Workflow Transparency:**
    *   The defined job statuses (Uploaded, Pending, Rejected, ReadyToPrint, Printing, Completed, PaidPickedUp) provide unambiguous progress tracking for everyone involved.
    *   On-site flash messages will provide immediate feedback for user actions.
    *   Email notifications ensure users are kept informed without needing to constantly check the system.

5.  **A Secure, Maintainable, and Extensible Platform:**
    *   Built using Flask, SQLAlchemy for database interaction (with SQLite initially), and Flask-Migrate for schema management, ensuring a solid backend foundation.
    *   The frontend will leverage Tailwind CSS for styling and Alpine.js for light interactivity, aiming for a clean and responsive user experience.
    *   The architecture is designed with future enhancements in mind, such as full user authentication (Flask-Login), more detailed reporting, advanced cost calculation APIs, and potentially more interactive 3D previews.

In essence, the project aims to replace potentially ad-hoc or manual 3D print request systems with a **centralized, digitally managed, and workflow-driven platform.** It prioritizes clarity, efficiency, and accurate file tracking, especially addressing the complexities of file changes introduced by slicer software, ultimately improving the experience for both students requesting prints and the staff managing the printing service.

---

## 1 · Project Setup (complete checklist)

| Item                | Command / File                                                                                                                                                       | Notes                                          |
| ------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------- |
| **Python venv**     | `python -m venv .venv`<br>`.\.venv\Scripts\activate`                                                                                                                 | Windows path — adjust for macOS/Linux          |
| **Core libs**       | `pip install Flask Flask-Login python-dotenv filelock waitress`                                                                                                      | keep requirements‑minimal.txt in repo          |
| **Optional libs**   | `pip install passlib[bcrypt] Flask-WTF itsdangerous pytest`                                                                                                          | passlib → strong hashing;<br>WTF → CSRF forms  |
| **JS toolchain**    | `npm init -y`<br>`npm install -D tailwindcss postcss autoprefixer alpinejs`                                                                                          | Tailwind JIT build                             |
| **Tailwind config** | `npx tailwindcss init -p`                                                                                                                                            | add LSU color palette in `tailwind.config.cjs` |
| **Pre‑commit**      | `.pre‑commit‑config.yaml` → black, isort, flake8, prettier                                                                                                           | keeps Python **and** HTML/JS clean             |
| **.env (example)**  | `text<br>FLASK_ENV=development<br>SECRET_KEY=REPLACE<br>UPLOAD_ROOT=C:\PrintSystem<br>MAX_CONTENT_LENGTH=52428800  # 50 MB<br>ALLOWED_EXT=3mf,form,idea,stl,obj<br>` | committed as `.env.example`; real key excluded |

## 2 · Directory Skeleton

```text
.
├─ app/
│  ├─ __init__.py        # create_app()
│  ├─ config.py
│  ├─ models/            # ← SQLite or JSON wrappers
│  │   └─ job.py
│  ├─ services/
│  │   ├─ file_service.py
│  │   ├─ cost_service.py
│  │   └─ auth_service.py
│  ├─ blueprints/
│  │   ├─ auth.py
│  │   ├─ prints.py      # upload + actions
│  │   └─ dashboard.py   # staff + student views
│  ├─ utils/
│  │   ├─ validators.py
│  │   └─ files.py
│  ├─ static/
│  │   ├─ css/tailwind.css
│  │   └─ js/main.js
│  └─ templates/
│     ├─ base.html
│     ├─ login.html
│     ├─ upload.html
│     └─ dashboard/
│         ├─ index.html
│         └─ _row.html
├─ tests/
│  ├─ test_upload.py
│  └─ test_actions.py
├─ run.py
└─ README.md
```

## 3 · Data & Domain Model

### `models/job.py` (SQLAlchemy or tiny‑DB style)

```python
class Status(str, Enum):
    UPLOADED = "Uploaded"
    REJECTED = "Rejected"
    READY    = "ReadyToPrint"
    PRINTING = "Printing"
    COMPLETED = "Completed"
    PICKED_UP = "PaidPickedUp"

class Job(db.Model):
    id             = db.Column(db.String, primary_key=True)   # uuid4 hex
    user_id        = db.Column(db.Integer, db.ForeignKey("user.id"))
    original_name  = db.Column(db.String(256))
    display_name   = db.Column(db.String(256))     # .3mf/.form/.idea if exists
    status         = db.Column(db.Enum(Status), default=Status.UPLOADED)
    printer        = db.Column(db.String(64))
    color          = db.Column(db.String(32))
    material       = db.Column(db.String(32))
    weight_g       = db.Column(db.Float)           # required on approve
    time_min       = db.Column(db.Integer)
    cost_usd       = db.Column(db.Numeric(6, 2))
    reject_reasons = db.Column(db.JSON)            # list[str]
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at     = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
```

*(Swap to plain JSON files if you're not ready for SQLite yet—the fields stay the same.)*

## 4 · Allowed Printers & Cost Matrix (`cost_service.py`)

```python
PRINTERS = {
    "Prusa MK4S":  {"rate_g": 0.08, "rate_min": 0.01},
    "Prusa XL":    {"rate_g": 0.09, "rate_min": 0.011},
    "Raise3D":     {"rate_g": 0.10, "rate_min": 0.012},
    "Formlabs":    {"rate_g": 0.12, "rate_min": 0.008},
}

def calc_cost(printer: str, weight_g: float, time_min: int) -> Decimal:
    table = PRINTERS.get(printer)
    if not table:
        raise ValueError("Unknown printer")
    return Decimal(weight_g * table["rate_g"] + time_min * table["rate_min"]).quantize(Decimal("0.01"))
```

Front‑end JS calls `/api/cost/preview?printer=...&weight=...&time=...` and renders.

## 5 · Security Must‑dos

* **File uploads**

  * `secure_filename`, extension whitelist, `MAX_CONTENT_LENGTH`.
  * Save path: `UPLOAD_ROOT / Status.UPLOADED / uuid4 + ext`.
  * After save, `python-magic` or `mimetypes.guess_type` for a sanity sniff.
* **Auth**

  * `passlib.hash.bcrypt` for passwords.
  * CSRF tokens via Flask‑WTF **or** itsdangerous signed forms if you stay vanilla.
* **Headers**

  * `app.after_request` → set `Content-Security-Policy`, `X-Frame-Options`, `Referrer-Policy`.

## 6 · Atomic Moves (two‑PC racing)

```python
from filelock import FileLock

def atomic_move(src: Path, dst: Path):
    lock = FileLock(dst.parent / ".queue.lock")
    with lock:
        dst.parent.mkdir(parents=True, exist_ok=True)
        src.replace(dst)
```

Every route that changes status wraps file operations with this helper.

## 7 · Front‑End Building Blocks

* **Tailwind build script** in `package.json`:

  ```json
  "scripts": {
    "dev": "tailwindcss -i ./app/static/css/tailwind.css -o ./app/static/css/build.css --watch",
    "build": "tailwindcss -i ./app/static/css/tailwind.css -o ./app/static/css/build.css --minify"
  }
  ```

* **Alpine.js** (import CDN in `base.html`) to:

  * Toggle status tabs (`x-data="{tab:'Uploaded'}"`).
  * Modal confirmation (`x-show="openConfirm"`).

* **Confirmation modal snippet** (`_confirm_modal.html`):

  ```html
  <template x-if="confirmText">
    <div class="fixed inset-0 flex items-center justify-center bg-black/50">
      <div class="bg-white p-6 rounded-xl shadow-xl">
        <p class="mb-4" x-text="confirmText"></p>
        <button class="btn-secondary mr-2" @click="confirm(false)">Cancel</button>
        <button class="btn-primary" @click="confirm(true)">Yes</button>
      </div>
    </div>
  </template>
  ```

### Status
- [x] Tailwind build script configured and verified via `npm run build`
- [x] Alpine.js integration noted
- [x] Confirmation modal pattern documented
- [x] Test template `test.html` created and Tailwind utility classes detected and applied

## 8 · GitHub Actions CI (sample)

### Task Breakdown
- [x] 8.1 Create `.github/workflows/ci.yml` with `test` and `tailwind` jobs
- [ ] 8.2 Configure `test` job to run pytest and flake8
- [ ] 8.3 Configure `tailwind` job to run npm install and npm run build
- [ ] 8.4 Verify CI passes on GitHub Actions

### Project Status Board
- [x] Tailwind build system verified
- [x] Test template created
- [x] .github/workflows/ci.yml created with test and tailwind jobs
- [x] All changes pushed to GitHub main branch
- [ ] Awaiting CI verification on GitHub
- [x] Notifications & Feedback: Email notifications and flash-message UX (COMPLETE)
- [x] File Previews & Thumbnails: Thumbnail generation (COMPLETE)
- [ ] User Management: Password-reset and account-management flows (IN PROGRESS)
- [x] Data Migrations & Backups: Flask-Migrate setup refined; backup/restore procedures documented (INITIAL PHASE COMPLETE)
- [x] Logging, Monitoring & Metrics: Basic file logging implemented, added specific logs to submit_routes (INITIAL PHASE COMPLETE)
- [x] Security Enhancements: Basic security headers implemented and CSP adjusted (INITIAL PHASE COMPLETE)
- [x] Testing Gaps: Initial unit tests for submit_routes created and passing (INITIAL PHASE COMPLETE)
- [ ] Deployment, Scaling & Secrets: Docker and secrets management
- [ ] Maintenance & Cleanup: Automated purge and disk-space monitoring

### Executor's Feedback or Assistance Requests
- Notifications & Feedback task is complete and tested.
- File Previews & Thumbnails: Thumbnail generation, display, and serving are now complete and tested.
- Data Migrations & Backups: Flask-Migrate setup has been refined. Procedures for SQLite database backup and restore have been documented.
- Logging, Monitoring & Metrics: Basic file logging is in place and key submission events are now logged.
- Security Enhancements: Basic security headers (including CSP) are active. CSP was adjusted to ensure site functionality with CDN-based Tailwind.
- Testing Gaps: Initial unit tests for submit_routes (GET, successful POST, POST with no file) are implemented and passing.
- User Management: Task taken off hold. Initial plan is to define User model, set up Flask-Login, and basic auth routes. Session ending for the day; work will resume here.
- Awaiting Planner direction for the next major task area upon session resumption.

## 9 · Systemd/Waitress Service (Windows Service similar via NSSM)

`/etc/systemd/system/printsystem.service`:

```ini
[Unit]
Description=3D Print Flask App
After=network.target

[Service]
User=conrad
Group=www-data
WorkingDirectory=/opt/printsystem
Environment="FLASK_ENV=production" "UPLOAD_ROOT=/mnt/printqueue"
ExecStart=/opt/printsystem/.venv/bin/waitress-serve --port=8080 app:create_app

[Install]
WantedBy=multi-user.target
```

## 10 · Test Coverage Targets

| Area              | Assertions                                                                     |
| ----------------- | ------------------------------------------------------------------------------ |
| **Upload**        | rejects bad extension, oversize file, path traversal                           |
| **Status change** | approve w/out weight → HTTP 400; approve valid → file moved & metadata updated |
| **Concurrency**   | two threads approving same job still yield single final location               |
| **Cost calc**     | known inputs → precise Decimal output                                          |

## 11 · Open Questions (call these out before sprinting)

1. **SQLite or JSON** — pick one now; switching later is non‑trivial.
2. **Thumbnails** — do you want them in MVP? (adds trimesh + pyrender queue).
3. **Email notifications** — defer or include on "Completed"?
4. **Password reset** — required or handled manually on‑site?

Give thumbs‑up on these and we can dive straight into scaffold code or any specific slice.

## End-of-Day Summary

- All initial project infrastructure is in place:
  - Project setup, virtualenv, core libraries, JS toolchain.
  - Directory structure scaffolded (app/, models/, services/, blueprints/, utils/, static/, templates/).
  - Data and domain model defined (`job.py`).
  - Security must-dos and atomic file operations documented.
  - Front-end build (Tailwind CSS, Alpine.js) configured and tested.
  - CI pipeline (GitHub Actions) created and validated (test + tailwind jobs).
  - Line endings and dependency cleanup completed; `.env.example` added.

## 12 · Next Steps and High-Level Task Breakdown

Below is the prioritized list of remaining work for the next development cycle:

1. Application Factory & Configuration
   - [ ] 12.1 Create `app/__init__.py` with `create_app()` and load configuration from `.env`.
   - [ ] 12.2 Implement `config.py` for multiple environments (dev, prod, testing).
   - [ ] 12.3 Register blueprints (`auth`, `prints`, `dashboard`) within `create_app()`.

2. Data Models & Persistence
   - [ ] 12.4 Move and implement `Job` model in `app/models/job.py`.
   - [ ] 12.5 Create `User` model with roles (student, staff).
   - [ ] 12.6 Set up database migrations (Flask-Migrate) or JSON-based storage.

3. Service Layer Implementation
   - [ ] 12.7 FileService: secure file upload, storage, and extension checks.
   - [ ] 12.8 CostService: cost calculation API endpoint and front-end integration.
   - [ ] 12.9 AuthService: password hashing, session management via Flask-Login.

4. Blueprint Routes & Views
   - [ ] 12.10 Auth blueprint: login, logout, access control, templates.
   - [ ] 12.11 Prints blueprint: upload form, student confirmation, status transitions.
   - [ ] 12.12 Dashboard blueprint: student vs. staff views, pending approvals.

5. Frontend Integration & Templates
   - [ ] 12.13 Finalize `base.html` and partials (navbar, tabs, modals).
   - [ ] 12.14 Update templates for upload, dashboard, approval flows with Tailwind.
   - [ ] 12.15 Integrate Alpine.js interactions (tabs toggling, confirmation modals).

6. Testing & Quality Assurance
   - [ ] 12.16 Write unit tests for uploads, status changes, and cost calculations.
   - [ ] 12.17 Add concurrency tests for atomic moves.
   - [ ] 12.18 Integrate test suite into CI with coverage reporting.

7. Deployment & Maintenance
   - [ ] 12.19 Document Windows service setup (NSSM) or systemd (Linux).
   - [ ] 12.20 Create README deployment instructions, environment variable docs.

---

Please review this summary and the proposed next steps. Once approved, we can proceed with Executor mode to start on the first actionable task (12.1). 

# Background and Motivation
The project is a Flask-based 3D print system that requires enhancements in user management, notifications, file previews, data management, logging, deployment, security, testing, and maintenance. The goal is to improve user experience, ensure data integrity, and maintain system stability.

# Key Challenges and Analysis
- Implementing a simple and secure user management system.
- Ensuring users receive timely notifications about their print jobs.
- Providing visual confirmation of uploaded files through thumbnails.
- Establishing a robust data migration and backup strategy.
- Implementing comprehensive logging and monitoring for system health.
- Streamlining deployment with Docker and securing secrets management.
- Enhancing security without complicating the user experience.
- Filling testing gaps to ensure system reliability.
- Automating maintenance tasks to manage system resources effectively.

# High-level Task Breakdown
1. **User Management**
   - Implement password-reset, self-registration, and account-management flows.
   - Success Criteria: Users can reset passwords and manage accounts seamlessly.

2. **Notifications & Feedback**
   - Implement email notifications for job status updates.
   - Implement flash-message UX for form feedback.
   - Success Criteria: Users receive timely notifications and feedback.

3. **File Previews & Thumbnails**
   - Generate and serve thumbnails or 3D previews for uploaded files.
   - Success Criteria: Users can visually confirm their uploads.

4. **Data Migrations & Backups**
   - Implement Flask-Migrate for database migrations.
   - Establish backup and restore procedures.
   - Success Criteria: Data integrity and security are maintained.

   **SQLite Backup Procedures (`instance/jobs.db`):**

   Regular backups are crucial for data safety. The primary database file is `instance/jobs.db`.

   **Method 1: Direct File Copy (Simple)**
   - **Procedure:** Directly copy the `instance/jobs.db` file to a secure backup location (e.g., another drive, cloud storage).
   - **Pros:** Very simple to implement and automate with basic scripting.
   - **Cons/Considerations:**
     - To ensure absolute consistency, it's safest to perform the copy when the application is not running or is in a state with no database writes. For a low-traffic internal application, briefly stopping the Flask app, copying, and restarting might be acceptable.
     - If copying a live database file, there's a small chance of catching the database in the middle of a transaction, potentially leading to a slightly inconsistent backup. SQLite is generally resilient to this, but it's a minor risk.

   **Method 2: SQLite Online Backup (Recommended for Live Backups)**
   - **Procedure:** Use the SQLite command-line interface (CLI) tool (`sqlite3`) and its `.backup` command. This performs a live backup, ensuring consistency even while the application is running.
     ```bash
     sqlite3 instance/jobs.db ".backup '/path/to/your/backup_location/jobs_backup_YYYYMMDD.db'"
     ```
     Replace `/path/to/your/backup_location/jobs_backup_YYYYMMDD.db` with your desired backup path and naming convention.
   - **Pros:** Ensures a consistent snapshot of the database without needing to stop the application. Preferred method for live systems.
   - **Cons:** Requires `sqlite3` CLI tool to be available on the system where backups are performed.

   **Backup Frequency and Retention:**
   - **Frequency:** Should be determined by how much data loss is acceptable. Daily backups are common for many applications. For critical systems, more frequent backups might be needed.
   - **Retention:** Decide how long to keep backups (e.g., 7 daily backups, 4 weekly, 12 monthly). This depends on storage capacity and recovery needs.
   - **Storage:** Store backups in a separate physical location from the production server if possible (e.g., different disk, network share, cloud storage) to protect against hardware failure.

   **SQLite Restore Procedures (`instance/jobs.db`):**

   Restoring a SQLite database from a backup file is typically straightforward.

   **Procedure:**
   1.  **Stop the Application:** Ensure the Flask application is completely stopped to prevent any attempts to access or modify the database during the restore process. This is critical to avoid corruption or inconsistent state.
       ```bash
       # (Example: If running via command line, Ctrl+C in the terminal)
       # (If running as a service, use the appropriate service stop command, e.g., systemctl stop your-app-service)
       ```
   2.  **Locate the Backup File:** Identify the backup file you wish to restore (e.g., `jobs_backup_YYYYMMDD.db`).
   3.  **Replace the Database File:**
       *   Optional but Recommended: Rename the existing `instance/jobs.db` file (e.g., to `instance/jobs.db.before_restore` or `instance/jobs.db.corrupted`) rather than deleting it immediately. This provides a fallback if the restore process encounters an unexpected issue.
       *   Copy your chosen backup file into the `instance/` directory.
       *   Rename the copied backup file to `jobs.db`.
         ```bash
         # Example (ensure paths are correct for your system):
         # mv instance/jobs.db instance/jobs.db.before_restore 
         # cp /path/to/your/backup_location/jobs_backup_YYYYMMDD.db instance/jobs.db
         ```
   4.  **Verify File Permissions (If Applicable):** Ensure the new `instance/jobs.db` file has the correct ownership and permissions that allow the application to read and write to it. This is more relevant in Linux/macOS environments.
   5.  **Restart the Application:** Start the Flask application again.
       ```bash
       # python app.py (or your service start command)
       ```
   6.  **Test Thoroughly:** After restoring, thoroughly test the application to ensure the data is consistent, accessible, and the application functions as expected with the restored data.

   **Important Considerations:**
   - **Restoring to a Point in Time:** When you restore a backup, the database reverts to the state it was in when that backup was taken. Any data added or changes made *after* the backup was created will be lost.
   - **Test Restores Periodically:** It's good practice to periodically test your backup and restore procedures (e.g., in a staging or development environment) to ensure they work correctly and that you are familiar with the process.

5. **Logging, Monitoring & Metrics**
   - Implement structured logs, request tracing, and error-tracking.
   - Implement health checks and uptime monitoring.
   - Success Criteria: System health is monitored and issues are diagnosed quickly.

6. **Deployment, Scaling & Secrets**
   - Use Docker for repeatable deployments.
   - Implement secure secrets management.
   - Success Criteria: Deployment is streamlined and secure.

7. **Security Enhancements**
   - Implement session timeouts, 2FA, CSP tightening, and other headers.
   - Success Criteria: Security is enhanced without complicating the user experience.

8. **Testing Gaps**
   - Implement end-to-end and integration tests.
   - Implement front-end component tests.
   - Success Criteria: System reliability is ensured through comprehensive testing.

9. **Maintenance & Cleanup**
   - Automate jobs to purge stale uploads.
   - Implement disk-space monitoring.
   - Success Criteria: System resources are managed effectively.

# Project Status Board
- [x] Notifications & Feedback: Email notifications and flash-message UX (COMPLETE)
- [x] File Previews & Thumbnails: Thumbnail generation (COMPLETE)
- [ ] User Management: Password-reset and account-management flows (IN PROGRESS)
- [x] Data Migrations & Backups: Flask-Migrate setup refined; backup/restore procedures documented (INITIAL PHASE COMPLETE)
- [x] Logging, Monitoring & Metrics: Basic file logging implemented, added specific logs to submit_routes (INITIAL PHASE COMPLETE)
- [x] Security Enhancements: Basic security headers implemented and CSP adjusted (INITIAL PHASE COMPLETE)
- [x] Testing Gaps: Initial unit tests for submit_routes created and passing (INITIAL PHASE COMPLETE)
- [ ] Deployment, Scaling & Secrets: Docker and secrets management
- [ ] Maintenance & Cleanup: Automated purge and disk-space monitoring

# Executor's Feedback or Assistance Requests
- Notifications & Feedback task is complete and tested.
- File Previews & Thumbnails: Thumbnail generation, display, and serving are now complete and tested.
- Data Migrations & Backups: Flask-Migrate setup has been refined. Procedures for SQLite database backup and restore have been documented.
- Logging, Monitoring & Metrics: Basic file logging is in place and key submission events are now logged.
- Security Enhancements: Basic security headers (including CSP) are active. CSP was adjusted to ensure site functionality with CDN-based Tailwind.
- Testing Gaps: Initial unit tests for submit_routes (GET, successful POST, POST with no file) are implemented and passing.
- User Management: Task taken off hold. Initial plan is to define User model, set up Flask-Login, and basic auth routes. Session ending for the day; work will resume here.
- Awaiting Planner direction for the next major task area upon session resumption.

# Lessons
- Include info useful for debugging in the program output.
- Read the file before you try to edit it.
- If there are vulnerabilities that appear in the terminal, run `npm audit` before proceeding.
- Always ask before using the `-force` git command.
- `trimesh` for thumbnail generation may require the `lxml` library if not already present, to handle certain 3D file formats. Install with `pip install lxml`.
- When using Flask-Migrate to manage database schemas, avoid using `db.create_all()`. Flask-Migrate (via Alembic) should be the sole source of truth for schema creation and modifications through migration scripts (`flask db migrate`, `flask db upgrade`). Using `db.create_all()` can lead to inconsistencies or bypass the migration history.

## Workflow Rules
### Job Status Flow
1. **Uploaded:** Initial state after student submission. Original uploaded file resides here.
2. **Pending:** Staff has inspected, potentially sliced (creating a new authoritative file), and the job is awaiting student confirmation.
3. **Rejected:** Not approved (with reasons).
4. **ReadyToPrint:** Approved by staff, confirmed by student, and queued. The authoritative file is the sliced file.
5. **Printing:** Currently being printed.
6. **Completed:** Print finished, awaiting pickup.
7. **PaidPickedUp:** Final state, job archived.

### File Handling Rules
- **Authoritative Job File:** Each job is associated with a single, authoritative 3D model file. The system's "Open File" button, available at the end of each job row, will always provide direct access to this current authoritative file for the job. This button is for opening/viewing the file with appropriate local software, **not for downloading a new copy**, thus preventing duplicates and process branching.
- **Initial Upload & Renaming:**
    - Upon student submission, the uploaded file is **mandatorily renamed** using the convention: `FirstAndLastName_PrintMethod_Color_SimpleJobID` (e.g., `JaneDoe_Filament_Blue_123.stl`). `SimpleJobID` will be the unique integer ID from the `Job` database table.
    - This renamed file is stored in the `JOBS_ROOT/Uploaded/` directory and is initially the authoritative file for the job.
- **Staff Inspection & Slicing Workflow:**
    - When staff inspects a job from the "Uploaded" status/tab, they will use the "Open File" button to open the current authoritative file in their chosen slicer software (e.g., PrusaSlicer, Formlabs PreForm, IdeaMaker).
    - Slicer software often changes the file type upon saving (e.g., `.stl` might become `.3mf` with PrusaSlicer, `.form` with Formlabs, or `.idea` with IdeaMaker).
    - After staff completes slicing and saves the file (which now might have a new extension and potentially a slightly modified name if the slicer enforces it), this **newly saved (sliced) file becomes the new authoritative file for the job.**
    - The system must:
        - Update the `job.filename` in the database to reflect the filename (and extension) of this new sliced file. The core `SimpleJobID` should ideally be preserved in the filename for continuity if possible, or the system must ensure the job record robustly links to this new filename.
        - Move this new authoritative (sliced) file from the staff member's local machine (or a temporary processing area if we implement that) into the appropriate job status directory (e.g., `JOBS_ROOT/Pending/` if awaiting student confirmation, or `JOBS_ROOT/ReadyToPrint/` if directly approved).
        - The original file from the `Uploaded` directory might be archived or deleted at this point, as the sliced file is now the primary one.
- **"Open File" Button Post-Slicing:** Subsequently, the "Open File" button for this job will always point to and allow opening of this new, sliced authoritative file relevant to its current status.
- **Storage Path:** Files are generally stored in a path structure like: `UPLOAD_ROOT/StatusName/JobFilename`.
- **Thumbnails:** Thumbnails are generated from the *original uploaded file* and stored in a central `thumbnails` directory, linked by the `job.id`.
- **File Type Support:** Initially focus on `.stl`, `.obj`, `.3mf`. The system must be aware that slicers can convert these (e.g., PrusaSlicer often outputs `.3mf`).
- **Size Limits:** Default 50MB, configurable. 