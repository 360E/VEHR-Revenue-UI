from datetime import datetime
from uuid import uuid4

from sqlalchemy.orm import Session

from app.db.models.audit_event import AuditEvent


def log_event(
    db: Session,
    action: str,
    entity_type: str,
    entity_id: str,
    organization_id: str | None = None,
    patient_id: str | None = None,
    actor: str | None = None,
) -> AuditEvent:
    event = AuditEvent(
        id=str(uuid4()),
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        organization_id=organization_id,
        patient_id=patient_id,
        created_at=datetime.utcnow(),
    )
    db.add(event)
    db.commit()
    return event
