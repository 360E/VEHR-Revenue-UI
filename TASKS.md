# TASKS.md — AI-Executable Backlog (Ordered by ROI)

> Each task is small, testable, and safe to delegate to Codex.
> Rule: **One task per PR/commit**. No “mega changes.”

## How to run locally (baseline)
- Backend: `python -m uvicorn app.main:app --reload`
- Frontend: `cd frontend && npm run dev`
- UI: `http://localhost:3000`
- API docs: `http://127.0.0.1:8000/docs`

---

## Task 01 — Add /health endpoint (Backend)
**Goal:** Health check for monitoring + stable deployments.

**Scope (allowed files):**
- `app/api/v1/endpoints/health.py` (new)
- `app/api/v1/router.py` (minimal include)

**Acceptance criteria:**
- `GET /health` returns `200` with `{ "status": "ok" }`
- No changes to `app/main.py` or `app/db/base.py`

---

## Task 02 — Frontend: Make patients table rows clickable
**Goal:** Clicking a patient navigates to chart page.

**Scope:**
- `frontend/src/app/patients/page.tsx`

**Acceptance criteria:**
- Clicking a row navigates to `/patients/<id>`
- No API changes

---

## Task 03 — Frontend: Patient chart page `/patients/[id]`
**Goal:** Real chart view for a patient.

**Scope:**
- `frontend/src/app/patients/[id]/page.tsx` (new)

**Acceptance criteria:**
- Fetches `GET /api/v1/patients/{id}`
- Shows name + demographics
- Handles loading + error states

---

## Task 04 — Frontend: Add Encounters tab on patient chart
**Goal:** Patient chart shows encounters.

**Scope:**
- `frontend/src/app/patients/[id]/page.tsx` (or split into components under `frontend/src/components/*`)

**Acceptance criteria:**
- Fetches `GET /api/v1/patients/{patient_id}/encounters`
- Renders list with encounter date + type (or whatever fields exist)
- Loading + empty state

---

## Task 05 — Frontend: Add Forms tab on patient chart
**Goal:** Patient chart shows form submissions.

**Scope:**
- patient chart page and/or components

**Acceptance criteria:**
- Fetches `GET /api/v1/patients/{patient_id}/forms`
- Shows submissions list with created_at + template id (or template name if available)
- Loading + empty state

---

## Task 06 — Frontend: List form templates page
**Goal:** Basic template browser.

**Scope:**
- `frontend/src/app/forms/templates/page.tsx` (new)

**Acceptance criteria:**
- Fetches `GET /api/v1/forms/templates`
- Displays name, version, status
- Loading + empty state

---

## Task 07 — Frontend: “Start Form” minimal flow (no schema rendering yet)
**Goal:** Submit a form with hardcoded sample data to validate UI→API pipeline.

**Scope:**
- Patient chart Forms tab (UI button)
- Uses existing `POST /api/v1/forms/submit`

**Acceptance criteria:**
- A button submits a test payload for selected template + patient_id
- UI displays success (submission id) and refreshes list

---

## Task 08 — Backend: Improve forms payloads to accept JSON objects (nice-to-have)
**Goal:** Remove double-escaped JSON strings.

**Scope (careful):**
- Pydantic schemas in forms endpoints only
- Models can still store as TEXT for now

**Acceptance criteria:**
- API accepts `schema` as JSON object (in addition to `schema_json` or replacing it)
- API accepts `submitted_data` as JSON object
- Backward compatibility: existing string fields still work OR a clean migration plan exists
- No changes to `app/main.py` or `app/db/base.py`

---

## Task 09 — Frontend: Basic dashboard layout + sidebar
**Goal:** App navigation feels like a product.

**Scope:**
- `frontend/src/app/layout.tsx`
- `frontend/src/components/sidebar.tsx` (new)

**Acceptance criteria:**
- Sidebar links: Patients, Form Templates
- Content renders within layout

---

## Task 10 — Backend: Documents foundation (storage + model)
**Goal:** Prepare for PDFs/uploads + SharePoint later.

**Scope (suggested):**
- `app/db/models/document.py` (new)
- endpoints for listing/attaching documents (minimal)
- do not implement actual external storage yet

**Acceptance criteria:**
- Document can be linked to patient and optionally encounter/form_submission
- API can list documents by patient
- Audit event recorded on create

---

## Task 11 — Events outbox (Integration-ready core)
**Goal:** Integration layer foundation without any vendor-specific code.

**Scope:**
- `app/db/models/event_outbox.py` (new)
- simple dispatcher stub

**Acceptance criteria:**
- When form submitted, an outbox event row is created (e.g., `form.submitted`)
- Admin endpoint to list outbox events
- No external calls yet

---

## Task 12 — Webhooks (first “integrates with anything” feature)
**Goal:** Outbound webhooks with retry.

**Acceptance criteria:**
- Tenant can configure a webhook URL (stored)
- Events are delivered to webhook
- Failures are logged + retried

---

## Task 13 — “Reference integration”: Teams notification OR SharePoint upload
**Goal:** Prove the connector pattern after outbox/webhooks exist.

**Acceptance criteria:**
- One connector only
- Vendor-agnostic framework remains intact
- Full audit trail of what was sent/uploaded

---

## Quality Gate (run after each task)
### Backend
- `python -m compileall app`
- run server and confirm `/docs` loads

### Frontend
- `cd frontend && npm run lint`
- `cd frontend && npm run build`
