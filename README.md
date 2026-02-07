VEHR (Veteran / Virtual Electronic Health Record)

VEHR is a modular FastAPI-based backend for an integrated EHR platform supporting Mental Health, Substance Use Disorder (SUD), Case Management, Medical, and Psychiatric services, with future support for auditing, billing, eligibility, forms, AI assistance, labs, fax, and CRM workflows.

This repository is the source of truth for architecture and run instructions.

🚀 Quick Start
1. Activate virtual environment
cd C:\VEHR
.\.venv\Scripts\Activate.ps1


You should see:

(.venv) PS C:\VEHR>

2. Run the server
python -m uvicorn app.main:app --reload

3. Open API docs

App: http://127.0.0.1:8000

Swagger docs: http://127.0.0.1:8000/docs

🧠 Core Architecture Rules (READ THIS FIRST)

These rules exist to prevent circular imports and startup failures.

SQLAlchemy base + models pattern (CRITICAL)
DO NOT VIOLATE THIS PATTERN

app/db/base.py

Defines Base only

Must NOT import any models

from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass


app/db/models/*.py

Each model imports Base

Models NEVER import each other directly unless necessary

app/db/models/__init__.py

Imports all models so SQLAlchemy registers tables

from app.db.models.patient import Patient  # noqa


app/main.py

On startup, explicitly imports app.db.models

THEN (optionally) runs Base.metadata.create_all(...) when AUTO_CREATE_TABLES=true

@app.on_event("startup")
def on_startup():
    import app.db.models  # register models
    if os.getenv("AUTO_CREATE_TABLES", "").strip().lower() in {"1", "true", "yes"}:
        Base.metadata.create_all(bind=engine)


👉 If you see errors like “partially initialized module”, this rule was broken.

📁 Project Structure
C:\VEHR
├── app
│   ├── __init__.py
│   ├── main.py
│   ├── api
│   │   └── v1
│   │       ├── router.py
│   │       └── endpoints
│   │           └── patients.py
│   ├── db
│   │   ├── base.py
│   │   ├── session.py
│   │   └── models
│   │       ├── __init__.py
│   │       └── patient.py
│   └── services
├── .venv
├── vehr.db
├── requirements.txt
└── README.md

🧪 Development Notes
Database

SQLite is used for local development (vehr.db)

Designed to be swappable to PostgreSQL later

Migrations (Alembic)

Local DB URL (default): sqlite:///./vehr.db
Actual path when running from repo root: C:\VEHR\vehr.db

Create the initial migration (first-time only):

alembic revision --autogenerate -m "init"

Apply migrations:

alembic upgrade head

Local DB workflow

1. Fresh start: delete or rename C:\VEHR\vehr.db, then run alembic upgrade head.
2. Existing DB already has tables: run alembic stamp head.

Optional dev-only fallback (not recommended for normal use):
set AUTO_CREATE_TABLES=true to allow Base.metadata.create_all() on startup.

Auth bootstrap (first-time only)

POST /api/v1/auth/bootstrap with:
{
  "organization_name": "The Daily Dose",
  "admin_email": "admin@example.com",
  "admin_password": "ChangeMeNow!",
  "admin_name": "Admin User"
}

Use the returned token as:
Authorization: Bearer <token>

Auto-reload

--reload is enabled for development

Server will restart on file changes

🤖 Codex / Copilot Usage Rules

To maintain accuracy and avoid regressions:

Allowed for Codex

New DB models

CRUD endpoints

Pydantic schemas

Refactors inside a single module

NOT allowed for Codex (without human review)

Architecture redesign

Compliance logic

Billing rules

Auth/permission models

Prompt discipline

One vertical slice at a time (Patients → Encounters → Audits → Forms)

Save prompts in codex_prompts/

🛠 Troubleshooting
Server won’t start

Confirm main.py is saved

Confirm .venv is activated

Run from C:\VEHR, not a subfolder

“Attribute app not found”

Ensure app = FastAPI(...) exists in main.py

Ensure app/__init__.py exists

Circular import error

Check base.py does NOT import models

Check models are only imported in models/__init__.py

Check main.py imports app.db.models on startup

📌 Roadmap (High Level)

✅ Patients (v1)

⏭ Encounters / Visits

⏭ Audit Events (compliance backbone)

⏭ Forms Engine (versioned, auditable, PDF)

⏭ Billing + Eligibility

⏭ AI-assisted documentation

⏭ Labs / Fax / CRM integrations

🧭 Runbook (When Coming Back Tomorrow)

Open VS Code

Open folder: C:\VEHR

Activate venv

Run uvicorn

Open /docs

Continue one module at a time

S3 presigned upload/download endpoints

Required env vars:

- AWS_REGION
- S3_BUCKET_NAME
- AWS_ACCESS_KEY_ID
- AWS_SECRET_ACCESS_KEY

Create presigned upload URL:

```bash
curl -X POST "http://127.0.0.1:8000/api/v1/uploads/presign" ^
  -H "Content-Type: application/json" ^
  -d "{\"filename\":\"intake-form.pdf\",\"content_type\":\"application/pdf\"}"
```

Upload using returned URL:

```bash
curl -X PUT "<url-from-presign-response>" ^
  -H "Content-Type: application/pdf" ^
  --data-binary "@intake-form.pdf"
```

Create presigned download URL:

```bash
curl "http://127.0.0.1:8000/api/v1/uploads/uploads/2026/02/<uuid>_intake-form.pdf/download"
```
