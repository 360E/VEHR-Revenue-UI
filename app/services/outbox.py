import json
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.event_outbox import EventOutbox
from app.services.webhooks import deliver_event_to_webhooks


def enqueue_event(db: Session, organization_id: str, event_type: str, payload: dict) -> EventOutbox:
    event = EventOutbox(
        organization_id=organization_id,
        event_type=event_type,
        payload_json=json.dumps(payload),
        status="pending",
        attempts=0,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def dispatch_pending_events(
    db: Session,
    limit: int = 25,
    organization_id: str | None = None,
) -> dict[str, int]:
    now = datetime.utcnow()
    query = select(EventOutbox).where(
        EventOutbox.status.in_(["pending", "retry"]),
        (EventOutbox.next_attempt_at.is_(None) | (EventOutbox.next_attempt_at <= now)),
    )
    if organization_id:
        query = query.where(EventOutbox.organization_id == organization_id)
    events = (
        db.execute(
            query.order_by(EventOutbox.created_at.asc()).limit(limit)
        )
        .scalars()
        .all()
    )

    processed = 0
    delivered = 0
    failed = 0

    for event in events:
        processed += 1
        ok = deliver_event_to_webhooks(db, event)
        event.attempts += 1
        event.last_attempt_at = now
        event.updated_at = now
        if ok:
            event.status = "delivered"
            event.next_attempt_at = None
            delivered += 1
        else:
            event.status = "retry"
            event.next_attempt_at = now + timedelta(minutes=min(60, 2 ** event.attempts))
            failed += 1
        db.add(event)
        db.commit()

    return {"processed": processed, "delivered": delivered, "failed": failed}
