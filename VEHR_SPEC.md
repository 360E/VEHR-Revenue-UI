# VEHR_SPEC.md — Single Source of Truth (SSOT)

> Purpose: Keep VEHR build consistent, safe, and scalable while delegating most implementation work to Codex/AI.
> This doc defines **scope, architecture, guardrails, coding standards, required endpoints, UI pages, and integration framework requirements**.

## 0) Current Baseline (as of 2026-02-03)
- Backend: **FastAPI** + **SQLAlchemy (DeclarativeBase)**
- Frontend: **Next.js (App Router)** in `/frontend` with a proxy rewrite to backend (`/api/* -> http://127.0.0.1:8000/api/*`)
- Implemented domains:
  - Patients
  - Encounters
  - Forms (Templates + Submissions, linked to Patient, optional Encounter)
  - Audit (event logging exists in some form—do not break it)

## 1) Product Principle
**VEHR is an EHR platform with an integrations layer** (events + connectors), not an EHR with bolt-on integrations.

## 2) Phases (ordered by ROI / risk reduction)
### Phase 1 — Core Clinical Engine (Foundation)
- Patients
- Encounters
- Forms Engine (linked; versioned templates)
- Audit trail
- Documents (PDFs + uploads)
- Tasks / workflow items
- Multi-tenant organizations + RBAC

### Phase 2 — Events & Automation (Integration-ready)
- Event registry + event persistence
- Outbound webhooks
- Retry + failure tracking
- Integration activity logs

### Phase 3 — Integrations Framework (Vendor-agnostic)
- Capabilities: Document Storage, Messaging, Telephony, Accounting exports, Scheduling, Fax, eSignature, SSO/IdP, Healthcare interop.
- Add connectors one at a time as “reference implementations” after the framework exists.

### Phase 4 — UI (Web App)
- Dashboard shell + sidebar nav
- Patient chart pages (tabs: Overview, Encounters, Forms, Documents, Audit)
- Forms runner UI (schema-driven)
- Admin screens (orgs, roles, integrations, audit)

### Phase 5 — Commercial Readiness
- Auth hardening
- Reporting + exports
- Deployment + backups
- Monitoring + incident response
- Pricing tiers aligned to capabilities

## 3) Architecture (High-level)
### Backend
- API-first service with versioned routes: `/api/v1`
- Persistence: SQLAlchemy ORM models
- Validation: Pydantic v2 schemas
- Audit-first: every meaningful write (and some reads) produces an audit event
- Prefer append/amend patterns over destructive edits

### Frontend
- Separate Next.js app under `/frontend`
- Use Next rewrites to avoid CORS in dev (`/api/*` proxied)
- App Router pages under `/frontend/src/app/*`
- Keep UI state simple; introduce state libraries later only if needed

## 4) Guardrails (Locked Files + Rules)
### Locked files (DO NOT modify unless explicitly requested)
- `app/main.py`
- `app/db/base.py`

### “Caution” files (modifications allowed but must be minimal and explained)
- `app/db/session.py` (or engine/session setup)
- `app/api/v1/router.py`
- `frontend/next.config.mjs`

### Non-negotiable rules
- Do not introduce circular imports in ORM models.
- Do not overwrite clinical history. Use addenda/amendments.
- All identifiers are UUID strings unless a specific reason exists.
- All timestamps are UTC.
- Any data export/integration action must be auditable.

## 5) Coding Standards
### Python
- Prefer explicit imports and clear module boundaries.
- Keep model declarations pure (no importing other models in base).
- Create “registry” imports in `app/db/models/__init__.py` to register models with `Base.metadata`.
- Use type hints where reasonable; avoid clever metaprogramming.

### TypeScript/Next.js
- Keep types for API responses near the consuming page or in a shared `/lib/api.ts`.
- Use `fetch("/api/...")` (proxied) rather than hardcoding backend URLs in UI.
- No heavy state management library until necessary.
- Error + loading states required for every network call.

## 6) Required API Endpoints (v1 baseline)
> These must remain stable; additions are OK.

### Patients
- `GET  /api/v1/patients`
- `POST /api/v1/patients`
- `GET  /api/v1/patients/{id}`

### Encounters
- `POST /api/v1/encounters`
- `GET  /api/v1/encounters/{encounter_id}`
- `GET  /api/v1/patients/{patient_id}/encounters`

### Forms
- `POST /api/v1/forms/templates`
- `GET  /api/v1/forms/templates`
- `GET  /api/v1/forms/templates/{template_id}`
- `POST /api/v1/forms/submit`
- `GET  /api/v1/forms/submissions/{submission_id}`
- `GET  /api/v1/patients/{patient_id}/forms`

### Health (to add soon)
- `GET /health` (returns `{ "status": "ok" }`)

## 7) UI Pages (minimum sellable flow)
### Must-have screens
- `/patients` — list
- `/patients/[id]` — patient chart page with tabs
- `/forms/templates` — list/create templates (basic)
- `/patients/[id]/forms` (or tab) — list + start a form
- `/encounters` or tabbed under patient

### “Feels like an EHR” milestone
- Click a patient → chart page → see encounters + forms list load.

## 8) Integrations Framework Requirements (vendor-agnostic)
### Capabilities
- Document Storage (SharePoint/Drive/Box)
- Messaging (Teams/Slack)
- Telephony (RingCentral/Dialpad/Twilio)
- Accounting export (QuickBooks/Xero)
- Scheduling (Outlook/Google)
- Fax (provider)
- eSignature (provider)
- SSO/IdP (Microsoft/Google/Okta)
- Healthcare interop (FHIR, clearinghouse, labs)

### Minimum platform features before adding connectors
- Integration connections table (tenant-scoped)
- Token/secret storage (encrypted-at-rest; stub locally)
- Event outbox + dispatcher
- Retry + failure logs
- Webhook delivery

## 9) Testing & Quality Gates (minimum)
### Backend
- `python -m compileall app`
- smoke test: start server and hit `/docs` and `/health`
- (later) pytest suite

### Frontend
- `npm run lint`
- `npm run build`

## 10) Deployment Note (later)
- Use Docker Compose for stable “demo/staging” instance.
- Keep dev local with hot reload.
