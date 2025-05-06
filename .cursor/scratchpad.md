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
- [ ] Awaiting push to GitHub and CI verification

### Executor's Feedback or Assistance Requests
- The initial CI workflow file has been created as per the plan. Next, push to GitHub and verify that the workflow runs and passes. If there are any issues, update the workflow accordingly.

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