import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models.clinical_audit_finding import ClinicalAuditFinding
from app.db.models.clinical_audit_run import ClinicalAuditRun
from app.db.models.document import Document
from app.db.models.encounter import Encounter
from app.db.models.form_submission import FormSubmission
from app.db.models.form_template import FormTemplate
from app.db.models.review_action import ReviewAction
from app.db.models.review_evidence_link import ReviewEvidenceLink
from app.db.models.review_queue_item import ReviewQueueItem
from app.services.audit import log_event
from app.core.time import utc_now


SUPPORTED_SUBJECT_TYPES = {"assessment", "treatment_plan", "encounter", "submission"}
SUPPORTED_MODES = {"deterministic_only", "deterministic_plus_ai"}
SUPPORTED_SEVERITIES = {"info", "warning", "high"}
SUPPORTED_QUEUE_STATUSES = {"open", "needs_correction", "resolved", "overridden"}
AUTO_QUEUE_RANK = {"info": 0, "warning": 1, "high": 2}


@dataclass
class _DimensionInput:
    key: str
    score_value: Any = None
    score_required: bool = True
    raw_reference: str | None = None


@dataclass
class _FindingDraft:
    signal_type: str
    severity: str
    finding_summary: str
    evidence_references: list[str] = field(default_factory=list)
    suggested_correction: str | None = None
    related_entities: dict[str, Any] = field(default_factory=dict)
    confidence_score: float | None = None


@dataclass
class ClinicalAuditRunOutcome:
    run: ClinicalAuditRun
    findings: list[ClinicalAuditFinding]
    auto_queue_items: list[ReviewQueueItem]

    @property
    def finding_count(self) -> int:
        return len(self.findings)

    @property
    def high_severity_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "high")

    @property
    def queue_count(self) -> int:
        return len(self.auto_queue_items)


def _json_loads(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _json_dumps(value: Any) -> str:
    return json.dumps(value, default=str)


def _normalize_dimension_key(raw_value: Any) -> str:
    text = str(raw_value or "").strip().lower()
    if not text:
        return ""
    normalized = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return normalized


def _moderate_threshold() -> float:
    raw = os.getenv("CLINICAL_AUDIT_MODERATE_SCORE_THRESHOLD", "2").strip()
    try:
        return float(raw)
    except ValueError:
        return 2.0


def _plan_window_days() -> int:
    raw = os.getenv("CLINICAL_AUDIT_PLAN_WINDOW_DAYS", "30").strip()
    try:
        days = int(raw)
    except ValueError:
        days = 30
    return max(1, min(days, 365))


def _auto_queue_min_severity() -> str:
    raw = os.getenv("CLINICAL_AUDIT_AUTO_QUEUE_MIN_SEVERITY", "high").strip().lower()
    if raw not in SUPPORTED_SEVERITIES:
        return "high"
    return raw


def _should_auto_queue(severity: str) -> bool:
    threshold = _auto_queue_min_severity()
    return AUTO_QUEUE_RANK.get(severity, 0) >= AUTO_QUEUE_RANK[threshold]


def _extract_dimensions(payload: dict[str, Any]) -> list[_DimensionInput]:
    raw_items: list[Any] = []

    dimensions = payload.get("dimensions")
    if isinstance(dimensions, list):
        raw_items.extend(dimensions)

    assessment = payload.get("assessment")
    if isinstance(assessment, dict) and isinstance(assessment.get("dimensions"), list):
        raw_items.extend(assessment["dimensions"])

    problem_areas = payload.get("problem_areas")
    if isinstance(problem_areas, list):
        raw_items.extend(problem_areas)

    normalized: list[_DimensionInput] = []
    for index, raw_item in enumerate(raw_items):
        if isinstance(raw_item, str):
            key = _normalize_dimension_key(raw_item)
            if key:
                normalized.append(
                    _DimensionInput(
                        key=key,
                        score_required=False,
                        raw_reference=f"dimensions[{index}]",
                    )
                )
            continue

        if not isinstance(raw_item, dict):
            continue

        key_source = (
            raw_item.get("key")
            or raw_item.get("id")
            or raw_item.get("name")
            or raw_item.get("problem")
            or raw_item.get("dimension")
            or raw_item.get("title")
            or raw_item.get("label")
        )
        key = _normalize_dimension_key(key_source)
        if not key:
            continue

        score_value = raw_item.get("score")
        for alternate_field in ("severity", "rating", "value", "level"):
            if score_value is None and alternate_field in raw_item:
                score_value = raw_item.get(alternate_field)

        score_required = bool(raw_item.get("score_required", raw_item.get("requires_score", True)))
        normalized.append(
            _DimensionInput(
                key=key,
                score_value=score_value,
                score_required=score_required,
                raw_reference=f"dimensions[{index}]",
            )
        )
    return normalized


def _score_needs_plan(score_value: Any) -> bool:
    if score_value is None:
        return False
    if isinstance(score_value, bool):
        return score_value
    if isinstance(score_value, (int, float)):
        return float(score_value) >= _moderate_threshold()

    text = str(score_value).strip().lower()
    if not text:
        return False
    if text in {"moderate", "high", "severe", "critical"}:
        return True
    try:
        numeric_score = float(text)
    except ValueError:
        return False
    return numeric_score >= _moderate_threshold()


def _extract_mapping_keys(raw_items: Any) -> set[str]:
    keys: set[str] = set()
    if not isinstance(raw_items, list):
        return keys

    for item in raw_items:
        if isinstance(item, str):
            key = _normalize_dimension_key(item)
            if key:
                keys.add(key)
            continue

        if not isinstance(item, dict):
            continue
        candidate = (
            item.get("key")
            or item.get("problem_area")
            or item.get("problem")
            or item.get("dimension")
            or item.get("name")
            or item.get("title")
            or item.get("label")
            or item.get("for")
        )
        key = _normalize_dimension_key(candidate)
        if key:
            keys.add(key)
    return keys


def _extract_treatment_plan_sets(payload: dict[str, Any]) -> dict[str, set[str]]:
    sections: list[dict[str, Any]] = [payload]
    nested_plan = payload.get("treatment_plan")
    if isinstance(nested_plan, dict):
        sections.append(nested_plan)

    problem_keys: set[str] = set()
    goal_keys: set[str] = set()
    intervention_keys: set[str] = set()

    for section in sections:
        problem_keys.update(_extract_mapping_keys(section.get("problem_areas")))
        problem_keys.update(_extract_mapping_keys(section.get("problems")))
        problem_keys.update(_extract_mapping_keys(section.get("dimensions")))
        goal_keys.update(_extract_mapping_keys(section.get("goals")))
        intervention_keys.update(_extract_mapping_keys(section.get("interventions")))

    return {
        "problem_keys": problem_keys,
        "goal_keys": goal_keys,
        "intervention_keys": intervention_keys,
    }


def _find_submission_pair(
    db: Session,
    *,
    organization_id: str,
    submission_id: str,
) -> tuple[FormSubmission, FormTemplate] | None:
    row = db.execute(
        select(FormSubmission, FormTemplate)
        .join(FormTemplate, FormSubmission.form_template_id == FormTemplate.id)
        .where(
            FormSubmission.id == submission_id,
            FormSubmission.organization_id == organization_id,
            FormTemplate.organization_id == organization_id,
        )
    ).first()
    if not row:
        return None
    return row[0], row[1]


def _find_treatment_plan_after_assessment(
    db: Session,
    *,
    organization_id: str,
    patient_id: str,
    assessment_created_at: datetime,
) -> tuple[FormSubmission, FormTemplate] | None:
    window_end = assessment_created_at + timedelta(days=_plan_window_days())
    row = db.execute(
        select(FormSubmission, FormTemplate)
        .join(FormTemplate, FormSubmission.form_template_id == FormTemplate.id)
        .where(
            FormSubmission.organization_id == organization_id,
            FormSubmission.patient_id == patient_id,
            FormSubmission.created_at >= assessment_created_at,
            FormSubmission.created_at <= window_end,
            func.lower(FormTemplate.name).like("%treatment%plan%"),
        )
        .order_by(FormSubmission.created_at.asc())
        .limit(1)
    ).first()
    if not row:
        return None
    return row[0], row[1]


def _find_latest_assessment_before_plan(
    db: Session,
    *,
    organization_id: str,
    patient_id: str,
    treatment_plan_created_at: datetime,
) -> tuple[FormSubmission, FormTemplate] | None:
    row = db.execute(
        select(FormSubmission, FormTemplate)
        .join(FormTemplate, FormSubmission.form_template_id == FormTemplate.id)
        .where(
            FormSubmission.organization_id == organization_id,
            FormSubmission.patient_id == patient_id,
            FormSubmission.created_at <= treatment_plan_created_at,
            func.lower(FormTemplate.name).like("%assessment%"),
        )
        .order_by(FormSubmission.created_at.desc())
        .limit(1)
    ).first()
    if not row:
        return None
    return row[0], row[1]


def _evaluate_assessment_submission(
    db: Session,
    *,
    organization_id: str,
    submission: FormSubmission,
    template: FormTemplate,
) -> tuple[dict[str, Any], list[_FindingDraft]]:
    assessment_payload = _json_loads(submission.submitted_data_json, {})
    related_entities: dict[str, Any] = {
        "patient_id": submission.patient_id,
        "encounter_id": submission.encounter_id,
        "submission_id": submission.id,
        "assessment_template_id": template.id,
    }
    finding_drafts: list[_FindingDraft] = []
    dimensions = _extract_dimensions(assessment_payload)

    if not dimensions:
        finding_drafts.append(
            _FindingDraft(
                signal_type="clinical_completeness",
                severity="high",
                finding_summary="Assessment submission is missing structured dimensions/problem areas.",
                evidence_references=["dimensions", "assessment.dimensions", "problem_areas"],
                suggested_correction="Capture required clinical dimensions in the assessment before finalizing.",
                related_entities=related_entities,
            )
        )
        return related_entities, finding_drafts

    for dimension in dimensions:
        if not dimension.score_required:
            continue
        has_score = dimension.score_value not in (None, "", [])
        if has_score:
            continue
        finding_drafts.append(
            _FindingDraft(
                signal_type="clinical_completeness",
                severity="warning",
                finding_summary=f"Dimension '{dimension.key}' is missing a required severity score.",
                evidence_references=[dimension.raw_reference or "dimensions"],
                suggested_correction="Add a severity/risk score for this dimension in the assessment.",
                related_entities=related_entities,
            )
        )

    plan_pair = _find_treatment_plan_after_assessment(
        db,
        organization_id=organization_id,
        patient_id=submission.patient_id,
        assessment_created_at=submission.created_at,
    )

    if not plan_pair:
        finding_drafts.append(
            _FindingDraft(
                signal_type="plan_alignment",
                severity="high",
                finding_summary=(
                    f"No treatment plan submission found within {_plan_window_days()} days "
                    "of this assessment."
                ),
                evidence_references=["form_templates:treatment_plan", "form_submissions.created_at"],
                suggested_correction="Create or link a treatment plan that addresses the assessed problems.",
                related_entities=related_entities,
            )
        )
        return related_entities, finding_drafts

    treatment_plan_submission, treatment_plan_template = plan_pair
    treatment_plan_payload = _json_loads(treatment_plan_submission.submitted_data_json, {})
    plan_sets = _extract_treatment_plan_sets(treatment_plan_payload)

    related_entities["treatment_plan_submission_id"] = treatment_plan_submission.id
    related_entities["treatment_plan_template_id"] = treatment_plan_template.id

    assessment_keys = {dimension.key for dimension in dimensions}
    missing_problem_refs = sorted(
        key for key in assessment_keys if key and key not in plan_sets["problem_keys"]
    )
    if missing_problem_refs:
        finding_drafts.append(
            _FindingDraft(
                signal_type="internal_consistency",
                severity="warning",
                finding_summary=(
                    "Treatment plan does not reference all assessment problem areas: "
                    + ", ".join(missing_problem_refs)
                ),
                evidence_references=["problem_areas", "goals", "interventions"],
                suggested_correction=(
                    "Align treatment plan problem areas with the assessment dimensions and document rationale."
                ),
                related_entities=related_entities,
            )
        )

    for dimension in dimensions:
        if not _score_needs_plan(dimension.score_value):
            continue
        has_goal = dimension.key in plan_sets["goal_keys"]
        has_intervention = dimension.key in plan_sets["intervention_keys"]
        if has_goal and has_intervention:
            continue
        finding_drafts.append(
            _FindingDraft(
                signal_type="plan_alignment",
                severity="high",
                finding_summary=(
                    f"Dimension '{dimension.key}' has moderate/high severity without a mapped "
                    "goal and intervention in treatment planning."
                ),
                evidence_references=["dimensions.score", "goals", "interventions"],
                suggested_correction=(
                    f"Add a measurable goal and intervention for '{dimension.key}' in the treatment plan."
                ),
                related_entities=related_entities,
            )
        )

    return related_entities, finding_drafts


def _evaluate_treatment_plan_submission(
    db: Session,
    *,
    organization_id: str,
    submission: FormSubmission,
    template: FormTemplate,
) -> tuple[dict[str, Any], list[_FindingDraft]]:
    treatment_plan_payload = _json_loads(submission.submitted_data_json, {})
    related_entities: dict[str, Any] = {
        "patient_id": submission.patient_id,
        "encounter_id": submission.encounter_id,
        "submission_id": submission.id,
        "treatment_plan_template_id": template.id,
    }
    finding_drafts: list[_FindingDraft] = []
    plan_sets = _extract_treatment_plan_sets(treatment_plan_payload)

    if not any(plan_sets.values()):
        finding_drafts.append(
            _FindingDraft(
                signal_type="clinical_completeness",
                severity="warning",
                finding_summary=(
                    "Treatment plan submission is missing structured problem areas, goals, or interventions."
                ),
                evidence_references=["problem_areas", "goals", "interventions"],
                suggested_correction="Document problem areas with corresponding goals/interventions.",
                related_entities=related_entities,
            )
        )

    assessment_pair = _find_latest_assessment_before_plan(
        db,
        organization_id=organization_id,
        patient_id=submission.patient_id,
        treatment_plan_created_at=submission.created_at,
    )
    if not assessment_pair:
        finding_drafts.append(
            _FindingDraft(
                signal_type="plan_alignment",
                severity="warning",
                finding_summary="No assessment submission was found before this treatment plan.",
                evidence_references=["assessment_submission.created_at", "treatment_plan.created_at"],
                suggested_correction="Link the treatment plan to a current assessment.",
                related_entities=related_entities,
            )
        )
        return related_entities, finding_drafts

    assessment_submission, assessment_template = assessment_pair
    assessment_payload = _json_loads(assessment_submission.submitted_data_json, {})
    dimensions = _extract_dimensions(assessment_payload)
    related_entities["assessment_submission_id"] = assessment_submission.id
    related_entities["assessment_template_id"] = assessment_template.id

    assessment_keys = {dimension.key for dimension in dimensions}
    missing_keys = sorted(
        key for key in assessment_keys if key and key not in plan_sets["problem_keys"]
    )
    if missing_keys:
        finding_drafts.append(
            _FindingDraft(
                signal_type="internal_consistency",
                severity="warning",
                finding_summary=(
                    "Treatment plan is missing assessed problem areas: " + ", ".join(missing_keys)
                ),
                evidence_references=["assessment.dimensions", "treatment_plan.problem_areas"],
                suggested_correction="Add missing assessed problem areas or document clinical justification.",
                related_entities=related_entities,
            )
        )

    return related_entities, finding_drafts


def _evaluate_subject(
    db: Session,
    *,
    organization_id: str,
    subject_type: str,
    subject_id: str,
) -> tuple[dict[str, Any], list[_FindingDraft]]:
    if subject_type in {"submission", "assessment", "treatment_plan"}:
        pair = _find_submission_pair(
            db,
            organization_id=organization_id,
            submission_id=subject_id,
        )
        if not pair:
            raise LookupError("Submission not found")
        submission, template = pair

        normalized_subject_type = subject_type
        if subject_type == "submission":
            template_name = template.name.lower()
            if "treatment" in template_name and "plan" in template_name:
                normalized_subject_type = "treatment_plan"
            elif "assessment" in template_name:
                normalized_subject_type = "assessment"
            else:
                normalized_subject_type = "assessment"

        if normalized_subject_type == "treatment_plan":
            return _evaluate_treatment_plan_submission(
                db,
                organization_id=organization_id,
                submission=submission,
                template=template,
            )

        return _evaluate_assessment_submission(
            db,
            organization_id=organization_id,
            submission=submission,
            template=template,
        )

    encounter = db.execute(
        select(Encounter).where(
            Encounter.id == subject_id,
            Encounter.organization_id == organization_id,
        )
    ).scalar_one_or_none()
    if not encounter:
        raise LookupError("Encounter not found")

    row = db.execute(
        select(FormSubmission, FormTemplate)
        .join(FormTemplate, FormSubmission.form_template_id == FormTemplate.id)
        .where(
            FormSubmission.organization_id == organization_id,
            FormSubmission.patient_id == encounter.patient_id,
            FormSubmission.encounter_id == encounter.id,
            func.lower(FormTemplate.name).like("%assessment%"),
        )
        .order_by(FormSubmission.created_at.desc())
        .limit(1)
    ).first()

    if not row:
        related_entities = {
            "encounter_id": encounter.id,
            "patient_id": encounter.patient_id,
        }
        return related_entities, [
            _FindingDraft(
                signal_type="clinical_completeness",
                severity="high",
                finding_summary="Encounter has no associated assessment submission.",
                evidence_references=["encounter_id", "form_submissions"],
                suggested_correction="Attach and complete an assessment submission for this encounter.",
                related_entities=related_entities,
            )
        ]

    submission, template = row[0], row[1]
    return _evaluate_assessment_submission(
        db,
        organization_id=organization_id,
        submission=submission,
        template=template,
    )


def _queue_due_at_for_severity(severity: str) -> datetime:
    if severity == "high":
        return utc_now() + timedelta(days=7)
    if severity == "warning":
        return utc_now() + timedelta(days=14)
    return utc_now() + timedelta(days=30)


def _actor_metadata(actor_user_id: str | None) -> dict[str, Any]:
    return {"actor_user_id": actor_user_id}


def create_or_get_queue_item_from_finding(
    db: Session,
    *,
    finding: ClinicalAuditFinding,
    actor_email: str | None,
    actor_user_id: str | None,
    auto_created: bool,
) -> ReviewQueueItem:
    existing = db.execute(
        select(ReviewQueueItem).where(
            ReviewQueueItem.organization_id == finding.organization_id,
            ReviewQueueItem.source_finding_id == finding.id,
        )
    ).scalar_one_or_none()
    if existing:
        return existing

    queue_item = ReviewQueueItem(
        organization_id=finding.organization_id,
        subject_type=finding.subject_type,
        subject_id=finding.subject_id,
        source_finding_id=finding.id,
        reason_code=finding.signal_type,
        severity=finding.severity,
        status="open",
        due_at=_queue_due_at_for_severity(finding.severity),
        created_at=utc_now(),
        updated_at=utc_now(),
    )
    db.add(queue_item)
    db.commit()
    db.refresh(queue_item)

    related_entities = _json_loads(finding.related_entities_json, {})
    log_event(
        db,
        action="review_queue_item.created_from_finding",
        entity_type="review_queue_item",
        entity_id=queue_item.id,
        organization_id=finding.organization_id,
        patient_id=related_entities.get("patient_id"),
        actor=actor_email or "system",
        metadata={
            **_actor_metadata(actor_user_id),
            "finding_id": finding.id,
            "auto_created": auto_created,
            "severity": finding.severity,
        },
    )
    return queue_item


def run_clinical_quality_audit(
    db: Session,
    *,
    organization_id: str,
    subject_type: str,
    subject_id: str,
    mode: str,
    actor_email: str | None,
    actor_user_id: str | None,
) -> ClinicalAuditRunOutcome:
    if subject_type not in SUPPORTED_SUBJECT_TYPES:
        raise ValueError("Unsupported subject type")
    if mode not in SUPPORTED_MODES:
        raise ValueError("Unsupported audit mode")

    run = ClinicalAuditRun(
        organization_id=organization_id,
        triggered_by_user_id=actor_user_id,
        subject_type=subject_type,
        subject_id=subject_id,
        related_entities_json="{}",
        mode=mode,
        status="started",
        started_at=utc_now(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    log_event(
        db,
        action="clinical_audit.run_started",
        entity_type="clinical_audit_run",
        entity_id=run.id,
        organization_id=organization_id,
        actor=actor_email or "system",
        metadata={
            **_actor_metadata(actor_user_id),
            "subject_type": subject_type,
            "subject_id": subject_id,
            "mode": mode,
        },
    )

    findings: list[ClinicalAuditFinding] = []
    auto_queue_items: list[ReviewQueueItem] = []
    related_entities: dict[str, Any] = {}

    try:
        related_entities, drafts = _evaluate_subject(
            db,
            organization_id=organization_id,
            subject_type=subject_type,
            subject_id=subject_id,
        )
        run.related_entities_json = _json_dumps(related_entities)
        db.commit()

        for draft in drafts:
            finding = ClinicalAuditFinding(
                organization_id=organization_id,
                run_id=run.id,
                signal_type=draft.signal_type,
                subject_type=subject_type,
                subject_id=subject_id,
                related_entities_json=_json_dumps(draft.related_entities or related_entities),
                severity=draft.severity,
                finding_summary=draft.finding_summary,
                evidence_references_json=_json_dumps(draft.evidence_references),
                suggested_correction=draft.suggested_correction,
                confidence_score=draft.confidence_score if mode == "deterministic_plus_ai" else None,
                created_at=utc_now(),
            )
            db.add(finding)
            db.commit()
            db.refresh(finding)
            findings.append(finding)

            finding_entities = _json_loads(finding.related_entities_json, {})
            log_event(
                db,
                action="clinical_audit.finding_created",
                entity_type="clinical_audit_finding",
                entity_id=finding.id,
                organization_id=organization_id,
                patient_id=finding_entities.get("patient_id"),
                actor=actor_email or "system",
                metadata={
                    **_actor_metadata(actor_user_id),
                    "run_id": run.id,
                    "signal_type": finding.signal_type,
                    "severity": finding.severity,
                },
            )

            if _should_auto_queue(finding.severity):
                queue_item = create_or_get_queue_item_from_finding(
                    db,
                    finding=finding,
                    actor_email=actor_email,
                    actor_user_id=actor_user_id,
                    auto_created=True,
                )
                auto_queue_items.append(queue_item)

        run.status = "completed"
        run.completed_at = utc_now()
        run.error_message = None
        db.commit()
        db.refresh(run)

        log_event(
            db,
            action="clinical_audit.run_completed",
            entity_type="clinical_audit_run",
            entity_id=run.id,
            organization_id=organization_id,
            patient_id=related_entities.get("patient_id"),
            actor=actor_email or "system",
            metadata={
                **_actor_metadata(actor_user_id),
                "status": run.status,
                "finding_count": len(findings),
                "high_severity_count": sum(1 for finding in findings if finding.severity == "high"),
                "queue_count": len(auto_queue_items),
            },
        )
        return ClinicalAuditRunOutcome(run=run, findings=findings, auto_queue_items=auto_queue_items)
    except Exception as exc:
        run.status = "failed"
        run.completed_at = utc_now()
        run.error_message = str(exc)
        run.related_entities_json = _json_dumps(related_entities)
        db.commit()

        log_event(
            db,
            action="clinical_audit.run_completed",
            entity_type="clinical_audit_run",
            entity_id=run.id,
            organization_id=organization_id,
            patient_id=related_entities.get("patient_id"),
            actor=actor_email or "system",
            metadata={
                **_actor_metadata(actor_user_id),
                "status": "failed",
                "error_message": str(exc),
                "finding_count": len(findings),
            },
        )
        raise


def update_review_queue_status(
    db: Session,
    *,
    queue_item: ReviewQueueItem,
    new_status: str,
    actor_email: str | None,
    actor_user_id: str | None,
    justification: str | None = None,
) -> ReviewQueueItem:
    if new_status not in SUPPORTED_QUEUE_STATUSES:
        raise ValueError("Invalid queue status")
    if new_status == "overridden" and not (justification or "").strip():
        raise ValueError("Override requires justification")

    queue_item.status = new_status
    queue_item.updated_at = utc_now()
    db.commit()
    db.refresh(queue_item)

    log_event(
        db,
        action="review_queue_item.status_changed",
        entity_type="review_queue_item",
        entity_id=queue_item.id,
        organization_id=queue_item.organization_id,
        actor=actor_email or "system",
        metadata={
            **_actor_metadata(actor_user_id),
            "status": new_status,
            "justification": justification,
        },
    )

    if new_status == "overridden":
        action = ReviewAction(
            organization_id=queue_item.organization_id,
            queue_item_id=queue_item.id,
            action_type="override",
            notes="Queue item overridden",
            justification=justification,
            created_by_user_id=actor_user_id,
            created_at=utc_now(),
        )
        db.add(action)
        db.commit()
        db.refresh(action)
        log_event(
            db,
            action="review_override.recorded",
            entity_type="review_action",
            entity_id=action.id,
            organization_id=queue_item.organization_id,
            actor=actor_email or "system",
            metadata={
                **_actor_metadata(actor_user_id),
                "queue_item_id": queue_item.id,
                "justification": justification,
            },
        )

    return queue_item


def create_review_action(
    db: Session,
    *,
    queue_item: ReviewQueueItem,
    action_type: str,
    notes: str | None,
    actor_email: str | None,
    actor_user_id: str | None,
) -> ReviewAction:
    action = ReviewAction(
        organization_id=queue_item.organization_id,
        queue_item_id=queue_item.id,
        action_type=action_type,
        notes=notes,
        created_by_user_id=actor_user_id,
        created_at=utc_now(),
    )
    db.add(action)
    db.commit()
    db.refresh(action)

    log_event(
        db,
        action="review_action.created",
        entity_type="review_action",
        entity_id=action.id,
        organization_id=queue_item.organization_id,
        actor=actor_email or "system",
        metadata={
            **_actor_metadata(actor_user_id),
            "queue_item_id": queue_item.id,
            "action_type": action_type,
        },
    )
    return action


def create_review_evidence_link(
    db: Session,
    *,
    queue_item: ReviewQueueItem,
    document_id: str,
    actor_email: str | None,
    actor_user_id: str | None,
) -> ReviewEvidenceLink:
    document = db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.organization_id == queue_item.organization_id,
        )
    ).scalar_one_or_none()
    if not document:
        raise LookupError("Document not found")

    existing = db.execute(
        select(ReviewEvidenceLink).where(
            ReviewEvidenceLink.organization_id == queue_item.organization_id,
            ReviewEvidenceLink.queue_item_id == queue_item.id,
            ReviewEvidenceLink.document_id == document_id,
        )
    ).scalar_one_or_none()
    if existing:
        return existing

    evidence_link = ReviewEvidenceLink(
        organization_id=queue_item.organization_id,
        queue_item_id=queue_item.id,
        document_id=document_id,
        created_by_user_id=actor_user_id,
        created_at=utc_now(),
    )
    db.add(evidence_link)
    db.commit()
    db.refresh(evidence_link)

    log_event(
        db,
        action="review_evidence_link.created",
        entity_type="review_evidence_link",
        entity_id=evidence_link.id,
        organization_id=queue_item.organization_id,
        actor=actor_email or "system",
        metadata={
            **_actor_metadata(actor_user_id),
            "queue_item_id": queue_item.id,
            "document_id": document_id,
        },
    )
    return evidence_link

