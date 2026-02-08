import json
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_membership, get_current_organization, require_permission
from app.db.models.clinical_audit_finding import ClinicalAuditFinding
from app.db.models.clinical_audit_run import ClinicalAuditRun
from app.db.models.review_action import ReviewAction
from app.db.models.review_evidence_link import ReviewEvidenceLink
from app.db.models.review_queue_item import ReviewQueueItem
from app.db.session import get_db
from app.core.time import utc_now
from app.services.clinical_audit import (
    SUPPORTED_QUEUE_STATUSES,
    create_or_get_queue_item_from_finding,
    create_review_action,
    create_review_evidence_link,
    run_clinical_quality_audit,
    update_review_queue_status,
)


router = APIRouter(tags=["Clinical Audit"])


class ClinicalAuditRunRequest(BaseModel):
    subject_type: Literal["assessment", "treatment_plan", "encounter", "submission"]
    subject_id: str = Field(min_length=1, max_length=100)
    mode: Literal["deterministic_only", "deterministic_plus_ai"] = "deterministic_only"


class ClinicalAuditRunSummary(BaseModel):
    run_id: str
    status: str
    finding_count: int
    high_severity_count: int
    queue_count: int


class ReviewQueueItemRead(BaseModel):
    id: str
    source_finding_id: str | None = None
    subject_type: str
    subject_id: str
    reason_code: str
    severity: str
    status: str
    assigned_to_user_id: str | None = None
    due_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClinicalAuditFindingRead(BaseModel):
    id: str
    run_id: str
    signal_type: str
    subject_type: str
    subject_id: str
    severity: str
    finding_summary: str
    evidence_references: list[str]
    related_entities: dict[str, Any]
    suggested_correction: str | None = None
    confidence_score: float | None = None
    created_at: datetime
    queue_item: ReviewQueueItemRead | None = None
    correction_checklist: list[str] = Field(default_factory=list)


class ClinicalAuditRunRead(BaseModel):
    id: str
    subject_type: str
    subject_id: str
    mode: str
    status: str
    related_entities: dict[str, Any]
    started_at: datetime
    completed_at: datetime | None = None
    error_message: str | None = None

    model_config = ConfigDict(from_attributes=True)


class ClinicalAuditRunDetail(ClinicalAuditRunRead):
    findings: list[ClinicalAuditFindingRead] = Field(default_factory=list)


class ReviewActionRead(BaseModel):
    id: str
    queue_item_id: str
    action_type: str
    notes: str | None = None
    justification: str | None = None
    created_by_user_id: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReviewEvidenceRead(BaseModel):
    id: str
    queue_item_id: str
    document_id: str
    created_by_user_id: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReviewQueueDetailRead(ReviewQueueItemRead):
    finding: ClinicalAuditFindingRead | None = None
    actions: list[ReviewActionRead] = Field(default_factory=list)
    evidence_links: list[ReviewEvidenceRead] = Field(default_factory=list)


class QueueStatusUpdateRequest(BaseModel):
    status: Literal["open", "needs_correction", "resolved", "overridden"]
    justification: str | None = None


class QueueActionCreateRequest(BaseModel):
    action_type: str = Field(min_length=1, max_length=50)
    notes: str | None = Field(default=None, max_length=4000)


class QueueEvidenceCreateRequest(BaseModel):
    document_id: str = Field(min_length=1, max_length=36)


def _json_load(value: str | None, fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return fallback


def _correction_checklist_for_finding(finding: ClinicalAuditFindingRead) -> list[str]:
    checklist = ["Review evidence references and confirm chart context."]
    if finding.signal_type == "clinical_completeness":
        checklist.append("Complete missing required fields and scoring dimensions.")
    if finding.signal_type == "plan_alignment":
        checklist.append("Map each moderate/high problem to a goal and intervention.")
    if finding.signal_type == "internal_consistency":
        checklist.append("Reconcile assessment problem areas with treatment plan sections.")
    if finding.suggested_correction:
        checklist.append(f"Implement suggested correction: {finding.suggested_correction}")
    return checklist


def _queue_item_read(queue_item: ReviewQueueItem | None) -> ReviewQueueItemRead | None:
    if not queue_item:
        return None
    return ReviewQueueItemRead.model_validate(queue_item)


def _finding_read(
    finding: ClinicalAuditFinding,
    queue_item: ReviewQueueItem | None = None,
) -> ClinicalAuditFindingRead:
    read = ClinicalAuditFindingRead(
        id=finding.id,
        run_id=finding.run_id,
        signal_type=finding.signal_type,
        subject_type=finding.subject_type,
        subject_id=finding.subject_id,
        severity=finding.severity,
        finding_summary=finding.finding_summary,
        evidence_references=_json_load(finding.evidence_references_json, []),
        related_entities=_json_load(finding.related_entities_json, {}),
        suggested_correction=finding.suggested_correction,
        confidence_score=finding.confidence_score,
        created_at=finding.created_at,
        queue_item=_queue_item_read(queue_item),
    )
    read.correction_checklist = _correction_checklist_for_finding(read)
    return read


def _run_read(run: ClinicalAuditRun) -> ClinicalAuditRunRead:
    return ClinicalAuditRunRead(
        id=run.id,
        subject_type=run.subject_type,
        subject_id=run.subject_id,
        mode=run.mode,
        status=run.status,
        related_entities=_json_load(run.related_entities_json, {}),
        started_at=run.started_at,
        completed_at=run.completed_at,
        error_message=run.error_message,
    )


def _queue_item_or_404(db: Session, organization_id: str, queue_item_id: str) -> ReviewQueueItem:
    queue_item = db.execute(
        select(ReviewQueueItem).where(
            ReviewQueueItem.id == queue_item_id,
            ReviewQueueItem.organization_id == organization_id,
        )
    ).scalar_one_or_none()
    if not queue_item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Queue item not found")
    return queue_item


@router.post("/clinical-audit/run", response_model=ClinicalAuditRunSummary)
def run_clinical_audit(
    payload: ClinicalAuditRunRequest,
    db: Session = Depends(get_db),
    organization=Depends(get_current_organization),
    membership=Depends(get_current_membership),
    _: None = Depends(require_permission("clinical_audit:run")),
) -> ClinicalAuditRunSummary:
    try:
        outcome = run_clinical_quality_audit(
            db,
            organization_id=organization.id,
            subject_type=payload.subject_type,
            subject_id=payload.subject_id,
            mode=payload.mode,
            actor_email=membership.user.email,
            actor_user_id=membership.user.id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    return ClinicalAuditRunSummary(
        run_id=outcome.run.id,
        status=outcome.run.status,
        finding_count=outcome.finding_count,
        high_severity_count=outcome.high_severity_count,
        queue_count=outcome.queue_count,
    )


@router.get("/clinical-audit/runs", response_model=list[ClinicalAuditRunRead])
def list_clinical_audit_runs(
    patient_id: str | None = None,
    encounter_id: str | None = None,
    subject_type: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    started_after: datetime | None = None,
    started_before: datetime | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    organization=Depends(get_current_organization),
    _: None = Depends(require_permission("clinical_audit:review")),
) -> list[ClinicalAuditRunRead]:
    query = select(ClinicalAuditRun).where(ClinicalAuditRun.organization_id == organization.id)
    if subject_type:
        query = query.where(ClinicalAuditRun.subject_type == subject_type)
    if status_filter:
        query = query.where(ClinicalAuditRun.status == status_filter)
    if started_after:
        query = query.where(ClinicalAuditRun.started_at >= started_after)
    if started_before:
        query = query.where(ClinicalAuditRun.started_at <= started_before)

    runs = (
        db.execute(query.order_by(ClinicalAuditRun.started_at.desc()).offset(offset).limit(limit))
        .scalars()
        .all()
    )
    filtered_runs: list[ClinicalAuditRunRead] = []
    for run in runs:
        related_entities = _json_load(run.related_entities_json, {})
        if patient_id and related_entities.get("patient_id") != patient_id:
            continue
        if encounter_id and related_entities.get("encounter_id") != encounter_id:
            continue
        filtered_runs.append(_run_read(run))
    return filtered_runs


@router.get("/clinical-audit/runs/{run_id}", response_model=ClinicalAuditRunDetail)
def get_clinical_audit_run(
    run_id: str,
    db: Session = Depends(get_db),
    organization=Depends(get_current_organization),
    _: None = Depends(require_permission("clinical_audit:review")),
) -> ClinicalAuditRunDetail:
    run = db.execute(
        select(ClinicalAuditRun).where(
            ClinicalAuditRun.id == run_id,
            ClinicalAuditRun.organization_id == organization.id,
        )
    ).scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    findings = (
        db.execute(
            select(ClinicalAuditFinding)
            .where(
                ClinicalAuditFinding.run_id == run.id,
                ClinicalAuditFinding.organization_id == organization.id,
            )
            .order_by(ClinicalAuditFinding.created_at.desc())
        )
        .scalars()
        .all()
    )
    queue_items = (
        db.execute(
            select(ReviewQueueItem).where(
                ReviewQueueItem.organization_id == organization.id,
                ReviewQueueItem.source_finding_id.in_([finding.id for finding in findings]) if findings else False,
            )
        )
        .scalars()
        .all()
    ) if findings else []
    queue_by_finding = {item.source_finding_id: item for item in queue_items}

    run_read = _run_read(run)
    return ClinicalAuditRunDetail(
        **run_read.model_dump(),
        findings=[_finding_read(finding, queue_by_finding.get(finding.id)) for finding in findings],
    )


@router.get("/clinical-audit/findings", response_model=list[ClinicalAuditFindingRead])
def list_clinical_audit_findings(
    severity: str | None = None,
    signal_type: str | None = None,
    subject_type: str | None = None,
    run_id: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    organization=Depends(get_current_organization),
    _: None = Depends(require_permission("clinical_audit:review")),
) -> list[ClinicalAuditFindingRead]:
    query = select(ClinicalAuditFinding).where(
        ClinicalAuditFinding.organization_id == organization.id
    )
    if severity:
        query = query.where(ClinicalAuditFinding.severity == severity)
    if signal_type:
        query = query.where(ClinicalAuditFinding.signal_type == signal_type)
    if subject_type:
        query = query.where(ClinicalAuditFinding.subject_type == subject_type)
    if run_id:
        query = query.where(ClinicalAuditFinding.run_id == run_id)

    findings = (
        db.execute(query.order_by(ClinicalAuditFinding.created_at.desc()).offset(offset).limit(limit))
        .scalars()
        .all()
    )
    if not findings:
        return []

    queue_items = (
        db.execute(
            select(ReviewQueueItem).where(
                ReviewQueueItem.organization_id == organization.id,
                ReviewQueueItem.source_finding_id.in_([finding.id for finding in findings]),
            )
        )
        .scalars()
        .all()
    )
    queue_by_finding = {item.source_finding_id: item for item in queue_items}

    response: list[ClinicalAuditFindingRead] = []
    for finding in findings:
        queue_item = queue_by_finding.get(finding.id)
        if status_filter and (not queue_item or queue_item.status != status_filter):
            continue
        response.append(_finding_read(finding, queue_item))
    return response


@router.post("/clinical-audit/findings/{finding_id}/queue", response_model=ReviewQueueItemRead)
def create_queue_item_from_finding(
    finding_id: str,
    db: Session = Depends(get_db),
    organization=Depends(get_current_organization),
    membership=Depends(get_current_membership),
    _: None = Depends(require_permission("clinical_audit:review")),
) -> ReviewQueueItemRead:
    finding = db.execute(
        select(ClinicalAuditFinding).where(
            ClinicalAuditFinding.id == finding_id,
            ClinicalAuditFinding.organization_id == organization.id,
        )
    ).scalar_one_or_none()
    if not finding:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Finding not found")

    queue_item = create_or_get_queue_item_from_finding(
        db,
        finding=finding,
        actor_email=membership.user.email,
        actor_user_id=membership.user.id,
        auto_created=False,
    )
    return ReviewQueueItemRead.model_validate(queue_item)


@router.get("/clinical-audit/queue", response_model=list[ReviewQueueItemRead])
def list_review_queue_items(
    severity: str | None = None,
    status_filter: str | None = Query(default=None, alias="status"),
    assigned_to_me: bool = False,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    organization=Depends(get_current_organization),
    membership=Depends(get_current_membership),
    _: None = Depends(require_permission("clinical_audit:review")),
) -> list[ReviewQueueItemRead]:
    query = select(ReviewQueueItem).where(ReviewQueueItem.organization_id == organization.id)
    if severity:
        query = query.where(ReviewQueueItem.severity == severity)
    if status_filter:
        if status_filter not in SUPPORTED_QUEUE_STATUSES:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid status")
        query = query.where(ReviewQueueItem.status == status_filter)
    if assigned_to_me:
        query = query.where(ReviewQueueItem.assigned_to_user_id == membership.user.id)

    queue_items = (
        db.execute(query.order_by(ReviewQueueItem.created_at.desc()).offset(offset).limit(limit))
        .scalars()
        .all()
    )
    return [ReviewQueueItemRead.model_validate(item) for item in queue_items]


@router.get("/clinical-audit/queue/{queue_item_id}", response_model=ReviewQueueDetailRead)
def get_review_queue_item(
    queue_item_id: str,
    db: Session = Depends(get_db),
    organization=Depends(get_current_organization),
    _: None = Depends(require_permission("clinical_audit:review")),
) -> ReviewQueueDetailRead:
    queue_item = _queue_item_or_404(db, organization.id, queue_item_id)

    finding = None
    if queue_item.source_finding_id:
        finding = db.execute(
            select(ClinicalAuditFinding).where(
                ClinicalAuditFinding.id == queue_item.source_finding_id,
                ClinicalAuditFinding.organization_id == organization.id,
            )
        ).scalar_one_or_none()

    actions = (
        db.execute(
            select(ReviewAction)
            .where(
                ReviewAction.queue_item_id == queue_item.id,
                ReviewAction.organization_id == organization.id,
            )
            .order_by(ReviewAction.created_at.desc())
        )
        .scalars()
        .all()
    )
    evidence_links = (
        db.execute(
            select(ReviewEvidenceLink)
            .where(
                ReviewEvidenceLink.queue_item_id == queue_item.id,
                ReviewEvidenceLink.organization_id == organization.id,
            )
            .order_by(ReviewEvidenceLink.created_at.desc())
        )
        .scalars()
        .all()
    )

    queue_read = ReviewQueueItemRead.model_validate(queue_item)
    return ReviewQueueDetailRead(
        **queue_read.model_dump(),
        finding=_finding_read(finding, queue_item) if finding else None,
        actions=[ReviewActionRead.model_validate(action) for action in actions],
        evidence_links=[
            ReviewEvidenceRead.model_validate(evidence_link) for evidence_link in evidence_links
        ],
    )


@router.post("/clinical-audit/queue/{queue_item_id}/assign-to-me", response_model=ReviewQueueItemRead)
def assign_queue_item_to_me(
    queue_item_id: str,
    db: Session = Depends(get_db),
    organization=Depends(get_current_organization),
    membership=Depends(get_current_membership),
    _: None = Depends(require_permission("clinical_audit:review")),
) -> ReviewQueueItemRead:
    queue_item = _queue_item_or_404(db, organization.id, queue_item_id)
    queue_item.assigned_to_user_id = membership.user.id
    queue_item.updated_at = utc_now()
    db.commit()
    db.refresh(queue_item)

    create_review_action(
        db,
        queue_item=queue_item,
        action_type="assigned_to_me",
        notes="Queue item assigned to current reviewer",
        actor_email=membership.user.email,
        actor_user_id=membership.user.id,
    )

    return ReviewQueueItemRead.model_validate(queue_item)


@router.post("/clinical-audit/queue/{queue_item_id}/status", response_model=ReviewQueueItemRead)
def update_queue_item_status(
    queue_item_id: str,
    payload: QueueStatusUpdateRequest,
    db: Session = Depends(get_db),
    organization=Depends(get_current_organization),
    membership=Depends(get_current_membership),
    _: None = Depends(require_permission("clinical_audit:review")),
) -> ReviewQueueItemRead:
    queue_item = _queue_item_or_404(db, organization.id, queue_item_id)
    try:
        updated_queue_item = update_review_queue_status(
            db,
            queue_item=queue_item,
            new_status=payload.status,
            actor_email=membership.user.email,
            actor_user_id=membership.user.id,
            justification=payload.justification,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return ReviewQueueItemRead.model_validate(updated_queue_item)


@router.post("/clinical-audit/queue/{queue_item_id}/actions", response_model=ReviewActionRead)
def add_queue_item_action(
    queue_item_id: str,
    payload: QueueActionCreateRequest,
    db: Session = Depends(get_db),
    organization=Depends(get_current_organization),
    membership=Depends(get_current_membership),
    _: None = Depends(require_permission("clinical_audit:review")),
) -> ReviewActionRead:
    queue_item = _queue_item_or_404(db, organization.id, queue_item_id)
    action = create_review_action(
        db,
        queue_item=queue_item,
        action_type=payload.action_type,
        notes=payload.notes,
        actor_email=membership.user.email,
        actor_user_id=membership.user.id,
    )
    return ReviewActionRead.model_validate(action)


@router.post("/clinical-audit/queue/{queue_item_id}/evidence", response_model=ReviewEvidenceRead)
def add_queue_item_evidence_link(
    queue_item_id: str,
    payload: QueueEvidenceCreateRequest,
    db: Session = Depends(get_db),
    organization=Depends(get_current_organization),
    membership=Depends(get_current_membership),
    _: None = Depends(require_permission("clinical_audit:review")),
) -> ReviewEvidenceRead:
    queue_item = _queue_item_or_404(db, organization.id, queue_item_id)
    try:
        evidence_link = create_review_evidence_link(
            db,
            queue_item=queue_item,
            document_id=payload.document_id,
            actor_email=membership.user.email,
            actor_user_id=membership.user.id,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return ReviewEvidenceRead.model_validate(evidence_link)

