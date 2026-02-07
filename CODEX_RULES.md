# CODEX_RULES.md — VEHR Guardrails for AI Changes

> Use this file as the “contract” for Codex/AI edits.
> Goal: move fast without breaking foundation.

## 1) Non‑Negotiable: Locked Files (DO NOT MODIFY)
- `app/main.py`
- `app/db/base.py`

If a task requires changes here, STOP and ask for explicit approval.

## 2) Allowed Change Scope (Default)
- Frontend: `frontend/src/app/**`, `frontend/src/components/**`, `frontend/src/lib/**`
- Backend endpoints: `app/api/v1/**`
- Backend schemas: `app/schemas/**` (if present)
- Backend models: `app/db/models/**` (ONLY when the task explicitly requires a new model)

## 3) One Task = One PR/Commit
- Implement exactly **one** task from `TASKS.md`.
- Do not “clean up” unrelated code.
- Do not refactor for style unless required for the task’s acceptance criteria.

## 4) Keep Contracts Stable
- Do not change existing endpoint paths, request/response shapes, or behavior unless the task explicitly says so.
- Add new endpoints rather than breaking existing ones.

## 5) Safety Rules (EHR)
- Never overwrite clinical history. Use append-only or explicit amendments/addenda.
- Any meaningful write action must create an audit event (or preserve existing audit behavior).
- IDs are UUID strings unless explicitly stated otherwise.
- Timestamps are UTC.

## 6) ORM / Import Rules (Prevent Circular Imports)
- Model files must not import `Base` from a module that imports models.
- Do not import models inside `app/db/base.py`.
- If registration is needed, use `app/db/models/__init__.py` to import models for metadata registration.

## 7) Frontend Network Rules
- Use `fetch("/api/...")` (proxied) — do not hardcode `http://127.0.0.1:8000` in UI code.
- Every API call must handle: loading, error, empty state.

## 8) Quality Gates (MUST PASS BEFORE DONE)
### Frontend
- `cd frontend && npm run lint`
- `cd frontend && npm run build`

### Backend
- `python -m compileall app`
- Start API and ensure `/docs` loads (and `/health` once implemented)

## 9) Output Required from Codex
- List files changed
- Brief explanation of changes
- How acceptance criteria was met
- How to test manually (1–3 steps)

## 10) If Uncertain, STOP
If requirements are ambiguous or a task conflicts with these rules:
- Do not guess.
- Ask for clarification or propose two options with tradeoffs.
