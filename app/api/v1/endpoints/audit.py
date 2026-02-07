from collections import Counter, defaultdict
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_organization, require_permission
from app.db.models.audit_event import AuditEvent
from app.db.session import get_db


router = APIRouter(tags=["Audit"])


WRITE_ACTION_HINTS = ("create", "update", "delete", "submit", "upload", "publish", "dispatch")
HIGH_RISK_ACTIONS = {
    "create_user",
    "bootstrap",
    "publish_form_template",
    "dispatch_outbox",
    "upload_document",
}


class AuditEventRead(BaseModel):
    id: str
    organization_id: str | None = None
    actor: str | None = None
    action: str
    entity_type: str
    entity_id: str
    patient_id: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AuditAggregateCount(BaseModel):
    key: str
    count: int


class AuditHourlyCount(BaseModel):
    hour_start: datetime
    count: int


class AuditSummaryRead(BaseModel):
    window_hours: int
    total_events: int
    by_action: list[AuditAggregateCount]
    by_entity_type: list[AuditAggregateCount]
    top_actors: list[AuditAggregateCount]
    hourly_activity: list[AuditHourlyCount]


class AuditAnomalyRead(BaseModel):
    kind: str
    severity: str
    description: str
    event_ids: list[str]
    related_actor: str | None = None
    sample_time: datetime


class AuditAssistantBriefRead(BaseModel):
    window_hours: int
    generated_at: datetime
    summary: str
    highlights: list[str]
    risk_score: int


def _window_start(hours: int) -> datetime:
    return datetime.now(UTC) - timedelta(hours=hours)


def _read_events_in_window(
    db: Session,
    organization_id: str,
    hours: int,
    limit: int = 6000,
) -> list[AuditEvent]:
    return (
        db.execute(
            select(AuditEvent)
            .where(
                AuditEvent.organization_id == organization_id,
                AuditEvent.created_at >= _window_start(hours),
            )
            .order_by(AuditEvent.created_at.desc())
            .limit(limit)
        )
        .scalars()
        .all()
    )


@router.get("/audit/events", response_model=list[AuditEventRead])
def list_audit_events(
    patient_id: str | None = None,
    entity_type: str | None = None,
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    organization=Depends(get_current_organization),
    _: None = Depends(require_permission("audit:read")),
) -> list[AuditEventRead]:
    query = select(AuditEvent).where(AuditEvent.organization_id == organization.id)
    if patient_id:
        query = query.where(AuditEvent.patient_id == patient_id)
    if entity_type:
        query = query.where(AuditEvent.entity_type == entity_type)

    events = (
        db.execute(query.order_by(AuditEvent.created_at.desc()).offset(offset).limit(limit))
        .scalars()
        .all()
    )
    return events


@router.get("/audit/summary", response_model=AuditSummaryRead)
def get_audit_summary(
    hours: int = Query(24, ge=1, le=720),
    db: Session = Depends(get_db),
    organization=Depends(get_current_organization),
    _: None = Depends(require_permission("audit:read")),
) -> AuditSummaryRead:
    events = _read_events_in_window(db, organization.id, hours)
    by_action = Counter(event.action for event in events)
    by_entity = Counter(event.entity_type for event in events)
    by_actor = Counter((event.actor or "system") for event in events)

    by_hour: dict[datetime, int] = defaultdict(int)
    for event in events:
        utc_time = event.created_at.replace(tzinfo=UTC)
        hour_start = utc_time.replace(minute=0, second=0, microsecond=0)
        by_hour[hour_start] += 1

    return AuditSummaryRead(
        window_hours=hours,
        total_events=len(events),
        by_action=[
            AuditAggregateCount(key=key, count=count)
            for key, count in by_action.most_common(10)
        ],
        by_entity_type=[
            AuditAggregateCount(key=key, count=count)
            for key, count in by_entity.most_common(10)
        ],
        top_actors=[
            AuditAggregateCount(key=key, count=count)
            for key, count in by_actor.most_common(10)
        ],
        hourly_activity=[
            AuditHourlyCount(hour_start=hour_start, count=count)
            for hour_start, count in sorted(by_hour.items())
        ],
    )


@router.get("/audit/anomalies", response_model=list[AuditAnomalyRead])
def list_audit_anomalies(
    hours: int = Query(72, ge=1, le=720),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    organization=Depends(get_current_organization),
    _: None = Depends(require_permission("audit:read")),
) -> list[AuditAnomalyRead]:
    events = _read_events_in_window(db, organization.id, hours, limit=8000)
    anomalies: list[AuditAnomalyRead] = []

    # Rule 1: burst activity for same actor/action in 15-minute bucket.
    burst_buckets: dict[tuple[str, str, datetime], list[AuditEvent]] = defaultdict(list)
    for event in events:
        actor = event.actor or "system"
        bucket_start = event.created_at.replace(
            minute=(event.created_at.minute // 15) * 15,
            second=0,
            microsecond=0,
        )
        burst_buckets[(actor, event.action, bucket_start)].append(event)

    for (actor, action, bucket_start), bucket_events in burst_buckets.items():
        if len(bucket_events) >= 5:
            anomalies.append(
                AuditAnomalyRead(
                    kind="burst_activity",
                    severity="high",
                    description=f"{len(bucket_events)} '{action}' events by {actor} in 15 minutes.",
                    event_ids=[event.id for event in bucket_events[:20]],
                    related_actor=actor,
                    sample_time=bucket_start.replace(tzinfo=UTC),
                )
            )

    # Rule 2: after-hours writes.
    for event in events:
        hour = event.created_at.hour
        if 6 <= hour < 20:
            continue
        if not any(token in event.action for token in WRITE_ACTION_HINTS):
            continue
        anomalies.append(
            AuditAnomalyRead(
                kind="after_hours_write",
                severity="medium",
                description=f"Action '{event.action}' recorded outside normal hours.",
                event_ids=[event.id],
                related_actor=event.actor,
                sample_time=event.created_at.replace(tzinfo=UTC),
            )
        )

    # Rule 3: high-risk actions.
    for event in events:
        if event.action not in HIGH_RISK_ACTIONS:
            continue
        anomalies.append(
            AuditAnomalyRead(
                kind="high_risk_action",
                severity="high",
                description=f"High-risk audit action observed: {event.action}.",
                event_ids=[event.id],
                related_actor=event.actor,
                sample_time=event.created_at.replace(tzinfo=UTC),
            )
        )

    severity_rank = {"high": 0, "medium": 1, "low": 2}
    anomalies = sorted(
        anomalies,
        key=lambda item: (severity_rank.get(item.severity, 99), item.sample_time),
        reverse=False,
    )
    return anomalies[:limit]


@router.get("/audit/assistant/brief", response_model=AuditAssistantBriefRead)
def get_audit_assistant_brief(
    hours: int = Query(24, ge=1, le=720),
    db: Session = Depends(get_db),
    organization=Depends(get_current_organization),
    _: None = Depends(require_permission("audit:read")),
) -> AuditAssistantBriefRead:
    events = _read_events_in_window(db, organization.id, hours)
    by_action = Counter(event.action for event in events)
    by_actor = Counter((event.actor or "system") for event in events)
    risk_events = [event for event in events if event.action in HIGH_RISK_ACTIONS]

    top_action = by_action.most_common(1)[0][0] if by_action else "none"
    top_actor = by_actor.most_common(1)[0][0] if by_actor else "system"
    write_events = [
        event for event in events if any(token in event.action for token in WRITE_ACTION_HINTS)
    ]

    risk_score = min(100, int((len(risk_events) * 12) + (len(write_events) * 0.3)))
    highlights: list[str] = [
        f"Total events in window: {len(events)}",
        f"Most frequent action: {top_action}",
        f"Most active actor: {top_actor}",
        f"High-risk actions observed: {len(risk_events)}",
    ]
    if not events:
        highlights.append("No events captured in selected window.")
    if len(risk_events) >= 3:
        highlights.append("Escalation suggested: review privileged actions and approvals.")

    summary = (
        f"Audit monitor reviewed the last {hours} hours. "
        f"{len(events)} events were recorded with focus on '{top_action}'. "
        f"Primary activity came from {top_actor}. "
        f"Risk score is {risk_score}/100."
    )

    return AuditAssistantBriefRead(
        window_hours=hours,
        generated_at=datetime.now(UTC),
        summary=summary,
        highlights=highlights,
        risk_score=risk_score,
    )
