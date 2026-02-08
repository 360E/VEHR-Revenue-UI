import json
from uuid import uuid4
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.audit_event import AuditEvent
from app.core.time import utc_now


def log_event(
    db: Session,
    action: str,
    entity_type: str,
    entity_id: str,
    organization_id: str | None = None,
    patient_id: str | None = None,
    actor: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AuditEvent:
    serialized_metadata: str | None = None
    if metadata is not None:
        serialized_metadata = json.dumps(metadata, default=str)

    event = AuditEvent(
        id=str(uuid4()),
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        organization_id=organization_id,
        patient_id=patient_id,
        metadata_json=serialized_metadata,
        created_at=utc_now(),
    )
    db.add(event)
    db.commit()
    return event



