from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import timedelta
from sqlalchemy import func, select

from app.db.models.clinical_audit_run import ClinicalAuditRun
from app.db.models.form_submission import FormSubmission
from app.db.models.form_template import FormTemplate
from app.db.session import SessionLocal
from app.services.clinical_audit import run_clinical_quality_audit
from app.core.time import utc_now


@dataclass
class RecheckSummary:
    scanned: int = 0
    triggered: int = 0
    skipped_recent_run: int = 0
    failed: int = 0


def _plan_window_days() -> int:
    raw = os.getenv("CLINICAL_AUDIT_PLAN_WINDOW_DAYS", "30").strip()
    try:
        value = int(raw)
    except ValueError:
        value = 30
    return max(1, min(value, 365))


def run() -> RecheckSummary:
    summary = RecheckSummary()
    db = SessionLocal()
    try:
        now = utc_now()
        cutoff = now - timedelta(days=_plan_window_days())

        rows = db.execute(
            select(FormSubmission, FormTemplate)
            .join(FormTemplate, FormSubmission.form_template_id == FormTemplate.id)
            .where(
                FormSubmission.organization_id.is_not(None),
                FormSubmission.created_at <= cutoff,
                func.lower(FormTemplate.name).like("%assessment%"),
            )
            .order_by(FormSubmission.created_at.asc())
        ).all()

        for submission, _template in rows:
            summary.scanned += 1

            existing_recent_run = db.execute(
                select(ClinicalAuditRun.id).where(
                    ClinicalAuditRun.organization_id == submission.organization_id,
                    ClinicalAuditRun.subject_type == "assessment",
                    ClinicalAuditRun.subject_id == submission.id,
                    ClinicalAuditRun.started_at >= now - timedelta(hours=24),
                )
            ).scalar_one_or_none()
            if existing_recent_run:
                summary.skipped_recent_run += 1
                continue

            try:
                run_clinical_quality_audit(
                    db,
                    organization_id=submission.organization_id,
                    subject_type="assessment",
                    subject_id=submission.id,
                    mode="deterministic_only",
                    actor_email="system",
                    actor_user_id=None,
                )
                summary.triggered += 1
            except Exception:
                summary.failed += 1

        return summary
    finally:
        db.close()


def main() -> None:
    summary = run()
    print(
        "clinical_audit_rechecks "
        f"scanned={summary.scanned} "
        f"triggered={summary.triggered} "
        f"skipped_recent_run={summary.skipped_recent_run} "
        f"failed={summary.failed}"
    )


if __name__ == "__main__":
    main()




