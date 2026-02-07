import json
from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_membership, get_current_organization, require_permission
from app.db.models.event_outbox import EventOutbox
from app.db.models.webhook_endpoint import WebhookEndpoint
from app.db.session import get_db
from app.services.audit import log_event
from app.services.outbox import dispatch_pending_events


router = APIRouter(tags=["Webhooks"])


class WebhookCreate(BaseModel):
    url: str
    event_types: list[str] | None = None
    signing_secret: str | None = None
    is_active: bool = True


class WebhookRead(BaseModel):
    id: str
    url: str
    event_types: list[str]
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class OutboxEventRead(BaseModel):
    id: str
    event_type: str
    status: str
    attempts: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


@router.get("/webhooks", response_model=list[WebhookRead])
def list_webhooks(
    db: Session = Depends(get_db),
    organization=Depends(get_current_organization),
    _: None = Depends(require_permission("webhooks:manage")),
) -> list[WebhookRead]:
    webhooks = (
        db.execute(
            select(WebhookEndpoint).where(WebhookEndpoint.organization_id == organization.id)
        )
        .scalars()
        .all()
    )
    return [
        WebhookRead(
            id=hook.id,
            url=hook.url,
            event_types=json.loads(hook.event_types_json or "[]"),
            is_active=hook.is_active,
            created_at=hook.created_at,
        )
        for hook in webhooks
    ]


@router.post("/webhooks", response_model=WebhookRead, status_code=status.HTTP_201_CREATED)
def create_webhook(
    payload: WebhookCreate,
    db: Session = Depends(get_db),
    organization=Depends(get_current_organization),
    membership=Depends(get_current_membership),
    _: None = Depends(require_permission("webhooks:manage")),
) -> WebhookRead:
    webhook = WebhookEndpoint(
        organization_id=organization.id,
        url=payload.url,
        event_types_json=json.dumps(payload.event_types or []),
        signing_secret=payload.signing_secret,
        is_active=payload.is_active,
    )
    db.add(webhook)
    db.commit()
    db.refresh(webhook)

    log_event(
        db,
        action="create_webhook",
        entity_type="webhook_endpoint",
        entity_id=webhook.id,
        organization_id=organization.id,
        actor=membership.user.email,
    )

    return WebhookRead(
        id=webhook.id,
        url=webhook.url,
        event_types=json.loads(webhook.event_types_json or "[]"),
        is_active=webhook.is_active,
        created_at=webhook.created_at,
    )


@router.get("/outbox/events", response_model=list[OutboxEventRead])
def list_outbox_events(
    db: Session = Depends(get_db),
    organization=Depends(get_current_organization),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    _: None = Depends(require_permission("webhooks:manage")),
) -> list[OutboxEventRead]:
    events = (
        db.execute(
            select(EventOutbox)
            .where(EventOutbox.organization_id == organization.id)
            .order_by(EventOutbox.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return events


@router.post("/outbox/dispatch")
def dispatch_outbox(
    db: Session = Depends(get_db),
    organization=Depends(get_current_organization),
    _: None = Depends(require_permission("webhooks:manage")),
) -> dict[str, int]:
    return dispatch_pending_events(db, organization_id=organization.id)
