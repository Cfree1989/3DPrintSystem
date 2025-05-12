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
- [x] Notifications & Feedback: Email notifications and flash-message UX (COMPLETE)
- [x] File Previews & Thumbnails: Thumbnail generation (COMPLETE)
- [x] User Management: Password-reset and account-management flows (COMPLETE)
  - [x] User model implementation
  - [x] Authentication forms
  - [x] Authentication templates
  - [x] Basic auth routes (login, logout, register)
  - [x] Password reset functionality
  - [x] Initial test suite
  - [x] Email service integration for password reset
  - [x] Integration tests for user flows
- [x] Data Migrations & Backups: Flask-Migrate setup refined; backup/restore procedures documented (COMPLETE)
- [x] Logging, Monitoring & Metrics: Basic file logging implemented, added specific logs to submit_routes (COMPLETE)
- [x] Security Enhancements: Basic security headers implemented and CSP adjusted (COMPLETE)
- [x] Testing Gaps: Initial unit tests for submit_routes created and passing (COMPLETE)
  - [x] Unit tests for User model and authentication
  - [x] Integration tests for user flows
  - [x] Tests for file management operations
- [x] Deployment, Scaling & Secrets: Docker and secrets management (COMPLETE)
  - [x] Development environment with docker-compose
  - [x] Production configuration with Nginx
  - [x] Environment variable management
  - [x] Volume management for persistent data
- [x] Maintenance & Cleanup: Automated purge and disk-space monitoring (COMPLETE)
  - [x] Implement cron job for stale upload cleanup
  - [x] Add disk space monitoring
  - [x] Create maintenance documentation
- [x] Job Management Workflow: Complete implementation (COMPLETE)
  - [x] Consolidated Job model with all required fields
  - [x] Updated dashboard with Alpine.js interactivity
  - [x] Proper file handling in approve/reject routes
  - [x] Status tracking and display
  - [x] File access controls
  - [x] Material, weight, and time input handling
  - [x] Cost calculation based on printer type

# Current Focus
Moving on to quality-of-life improvements:
- [ ] Client-side file validation
- [ ] Upload progress bar
- [ ] File type icons
- [ ] Job list sorting and filtering
- [ ] Basic search functionality
- [ ] Print time estimation

# Executor's Progress Report

I've completed a major refactoring to eliminate redundancies and improve code organization:

1. **File Management Improvements**
   - Created centralized `FileService` class
   - Implemented secure file operations with proper error handling
   - Added file locking for concurrent operations
   - Moved file operations from routes to service layer

2. **Email System Improvements**
   - Created centralized `EmailService` class
   - Added HTML email templates
   - Improved error handling and logging
   - Added job status notification emails

3. **Thumbnail Generation Improvements**
   - Created dedicated `ThumbnailService` class
   - Improved 3D model rendering with better lighting
   - Added error handling and logging
   - Moved thumbnails to static directory for better caching

4. **Route Organization**
   - Consolidated redundant routes into main blueprint
   - Improved route naming consistency
   - Added proper authorization checks
   - Improved error handling and user feedback

5. **Code Cleanup**
   - Removed redundant models.py
   - Eliminated duplicate route definitions
   - Standardized status handling
   - Improved type hints and documentation

### Lessons

1. Always use service classes to encapsulate related functionality
2. Implement proper file locking for concurrent operations
3. Use static directory for serving generated assets
4. Add comprehensive error handling and logging
5. Use type hints for better code maintainability
6. Keep route handlers thin, move business logic to services
7. Use HTML templates for better email presentation
8. Implement proper authorization checks on all routes
9. Use proper file path handling with Path objects
10. Add proper documentation for all classes and methods

### Next Steps

1. [ ] Add unit tests for new service classes
2. [ ] Implement rate limiting for file uploads
3. [ ] Add file cleanup cron job
4. [ ] Implement file type validation
5. [ ] Add progress tracking for long operations
6. [ ] Implement proper session handling
7. [ ] Add API documentation
8. [ ] Set up monitoring and alerting
9. [ ] Implement backup strategy
10. [ ] Add performance metrics

### Project Status Board

- [x] File Management
  - [x] Centralized file service
  - [x] Secure file operations
  - [x] File locking
  - [x] Error handling
  - [x] Path standardization

- [x] Email System
  - [x] Centralized email service
  - [x] HTML templates
  - [x] Error handling
  - [x] Status notifications
  - [x] Async sending

- [x] Thumbnail Generation
  - [x] Dedicated service
  - [x] Improved rendering
  - [x] Error handling
  - [x] Static file serving
  - [x] Caching support

- [x] Route Organization
  - [x] Consolidated routes
  - [x] Authorization checks
  - [x] Error handling
  - [x] User feedback
  - [x] Consistent naming

### Executor's Feedback or Assistance Requests

1. Need to verify if we should add more file type validations
2. Consider implementing file upload progress tracking
3. Review email templates for accessibility
4. Consider adding rate limiting for API endpoints
5. Review backup strategy for uploaded files

Would you like me to proceed with implementing any of the next steps?

# Lessons
- Include info useful for debugging in the program output.
- Read the file before you try to edit it.
- If there are vulnerabilities that appear in the terminal, run `npm audit` before proceeding.
- Always ask before using the `-force` git command.
- `trimesh` for thumbnail generation may require the `lxml` library if not already present, to handle certain 3D file formats. Install with `pip install lxml`.
- When using Flask-Migrate to manage database schemas, avoid using `db.create_all()`. Flask-Migrate (via Alembic) should be the sole source of truth for schema creation and modifications through migration scripts (`flask db migrate`, `flask db upgrade`). Using `db.create_all()` can lead to inconsistencies or bypass the migration history.
- For initial database setup when migrations aren't detecting models, you may need to use `db.create_all()` to create the initial tables, but after that, switch to using Flask-Migrate for all schema changes.

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

## SQLAlchemy Relationship Fix Plan

### Current Issue
The User and Job models have a circular relationship definition causing conflicts:
- User model defines: `jobs = db.relationship('Job', lazy='dynamic')`
- Job model defines: `user = db.relationship('User', backref=db.backref('jobs', lazy=True))`

This creates a conflict because both are trying to define the 'jobs' relationship.

### Solution Steps
1. **Simplify Relationship Definition**
   - Keep the foreign key in Job model: `user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)`
   - Define the relationship only once in the User model with backref
   - Remove redundant relationship definition from Job model
   - Update any code that relies on these relationships

2. **Implementation Plan**
   a. Modify User model:
      ```python
      # In User model
      jobs = db.relationship('Job', backref='user', lazy='dynamic')
      ```
   
   b. Modify Job model:
      - Remove the explicit relationship definition
      - Keep only the foreign key column
      
3. **Testing**
   - Run the test suite to verify relationship works
   - Test job creation and querying from both sides
   - Verify cascade operations work as expected

4. **Success Criteria**
   - All tests pass
   - Can create jobs and associate with users
   - Can query jobs from user instances
   - Can access user from job instances
   - No SQLAlchemy relationship errors

### Next Steps
1. Implement the changes in User and Job models
2. Run database migrations if needed
3. Update any affected tests
4. Verify functionality in the application 

## 9 · Final Improvements

### Quality of Life Features
- [ ] 9.1 Add file size validation on the client side before upload
- [ ] 9.2 Implement progress bar for file uploads
- [ ] 9.3 Add file type icons in the job list for different supported formats
- [ ] 9.4 Add sorting and filtering options in the jobs list
- [ ] 9.5 Implement a basic search functionality
- [ ] 9.6 Add print time estimation based on file size and printer selection

### Documentation
- [ ] 9.7 Create user documentation
- [ ] 9.8 Create staff/admin documentation
- [ ] 9.9 Add API documentation for future integrations

### Performance & Optimization
- [ ] 9.10 Implement client-side caching for static assets
- [ ] 9.11 Add database indexing for frequently accessed fields
- [ ] 9.12 Optimize thumbnail generation process
- [ ] 9.13 Implement lazy loading for job list items

### Monitoring & Analytics
- [ ] 9.14 Add basic analytics for print job statistics
- [ ] 9.15 Implement printer utilization tracking
- [ ] 9.16 Add cost analysis reports
- [ ] 9.17 Create dashboard for system health monitoring

# Current Focus
Starting with client-side improvements to enhance user experience, particularly the file upload process. 