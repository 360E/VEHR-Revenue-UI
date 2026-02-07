# PROMPTS.md — Ready-to-run Codex Prompts (Tasks 01–10)

> Copy/paste the prompt for the task you want.
> Always ensure Codex reads: **VEHR_SPEC.md**, **TASKS.md**, **CODEX_RULES.md**.
> Rule: **One task per run**.

---

## Prompt 01 — Task 01 (/health endpoint)
Read `VEHR_SPEC.md`, `TASKS.md`, and `CODEX_RULES.md`.
Implement **Task 01** exactly as written: add `GET /health` returning `{ "status": "ok" }` with HTTP 200.
**Do not modify** `app/main.py` or `app/db/base.py`.
Keep changes minimal. Output:
1) files changed,
2) why,
3) how acceptance criteria was met,
4) manual test steps.

---

## Prompt 02 — Task 02 (clickable patient rows)
Read `VEHR_SPEC.md`, `TASKS.md`, and `CODEX_RULES.md`.
Implement **Task 02** exactly as written: make rows clickable in `frontend/src/app/patients/page.tsx` to navigate to `/patients/<id>`.
Do not change backend code. Keep changes minimal.
Output files changed + manual test steps.

---

## Prompt 03 — Task 03 (patient chart page)
Read `VEHR_SPEC.md`, `TASKS.md`, and `CODEX_RULES.md`.
Implement **Task 03** exactly as written: create `frontend/src/app/patients/[id]/page.tsx`.
Fetch `GET /api/v1/patients/{id}` using `fetch("/api/v1/patients/"+id)` (proxied).
Show demographics, loading, error states.
Do not modify backend code.
Output files changed + manual test steps.

---

## Prompt 04 — Task 04 (encounters tab)
Read `VEHR_SPEC.md`, `TASKS.md`, and `CODEX_RULES.md`.
Implement **Task 04** exactly as written: add an Encounters tab/section to the patient chart.
Fetch `GET /api/v1/patients/{patient_id}/encounters`.
Render list with date + any available fields; include loading and empty states.
Do not modify backend code.
Output files changed + manual test steps.

---

## Prompt 05 — Task 05 (forms tab)
Read `VEHR_SPEC.md`, `TASKS.md`, and `CODEX_RULES.md`.
Implement **Task 05** exactly as written: add a Forms tab/section to the patient chart.
Fetch `GET /api/v1/patients/{patient_id}/forms`.
Render submissions list with created_at + template id/name if available; include loading and empty states.
Do not modify backend code.
Output files changed + manual test steps.

---

## Prompt 06 — Task 06 (form templates list page)
Read `VEHR_SPEC.md`, `TASKS.md`, and `CODEX_RULES.md`.
Implement **Task 06** exactly as written: create `frontend/src/app/forms/templates/page.tsx`.
Fetch `GET /api/v1/forms/templates`.
Render list with name, version, status; loading + empty state.
Do not modify backend code.
Output files changed + manual test steps.

---

## Prompt 07 — Task 07 (start form minimal submit)
Read `VEHR_SPEC.md`, `TASKS.md`, and `CODEX_RULES.md`.
Implement **Task 07** exactly as written: add a “Start Form” button in the patient Forms tab that submits a hardcoded example payload to `POST /api/v1/forms/submit` and refreshes the submissions list.
Do not implement schema-driven form rendering yet.
Do not modify backend code.
Output files changed + manual test steps.

---

## Prompt 08 — Task 08 (backend JSON objects for forms)
Read `VEHR_SPEC.md`, `TASKS.md`, and `CODEX_RULES.md`.
Implement **Task 08** exactly as written: allow forms endpoints to accept JSON objects (not only JSON strings) for schema/submitted_data.
Maintain backward compatibility OR provide a clean migration plan.
**Do not modify** `app/main.py` or `app/db/base.py`.
Output files changed + manual test steps.

---

## Prompt 09 — Task 09 (sidebar layout)
Read `VEHR_SPEC.md`, `TASKS.md`, and `CODEX_RULES.md`.
Implement **Task 09** exactly as written: add a basic dashboard layout in `frontend/src/app/layout.tsx` and a sidebar component.
Sidebar links: Patients, Form Templates.
Keep styling minimal and clean. Do not modify backend code.
Output files changed + manual test steps.

---

## Prompt 10 — Task 10 (documents foundation backend)
Read `VEHR_SPEC.md`, `TASKS.md`, and `CODEX_RULES.md`.
Implement **Task 10** exactly as written: add a minimal Document model linked to patient (and optional encounter/form submission), plus an endpoint to list documents by patient.
Ensure an audit event is recorded on create.
**Do not modify** `app/main.py` or `app/db/base.py`.
Output files changed + manual test steps.
