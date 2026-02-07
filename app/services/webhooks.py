import hmac
import json
from hashlib import sha256

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.event_outbox import EventOutbox
from app.db.models.webhook_delivery import WebhookDelivery
from app.db.models.webhook_endpoint import WebhookEndpoint


def _event_matches(webhook: WebhookEndpoint, event_type: str) -> bool:
    try:
        configured = json.loads(webhook.event_types_json or "[]")
    except json.JSONDecodeError:
        configured = []
    if not configured:
        return True
    return event_type in configured


def _sign_payload(secret: str, body: bytes) -> str:
    return hmac.new(secret.encode("utf-8"), body, sha256).hexdigest()


def deliver_event_to_webhooks(db: Session, event: EventOutbox) -> bool:
    webhooks = (
        db.execute(
            select(WebhookEndpoint).where(
                WebhookEndpoint.organization_id == event.organization_id,
                WebhookEndpoint.is_active.is_(True),
            )
        )
        .scalars()
        .all()
    )

    if not webhooks:
        return True

    payload = {
        "id": event.id,
        "type": event.event_type,
        "organization_id": event.organization_id,
        "created_at": event.created_at.isoformat(),
        "payload": json.loads(event.payload_json),
    }
    body = json.dumps(payload).encode("utf-8")

    all_ok = True
    for webhook in webhooks:
        if not _event_matches(webhook, event.event_type):
            continue

        headers = {
            "Content-Type": "application/json",
            "X-VEHR-Event": event.event_type,
        }
        if webhook.signing_secret:
            headers["X-VEHR-Signature"] = _sign_payload(webhook.signing_secret, body)

        status = "failed"
        response_code = None
        response_body = None
        try:
            response = httpx.post(webhook.url, content=body, headers=headers, timeout=10.0)
            response_code = response.status_code
            response_body = response.text[:1000] if response.text else None
            if 200 <= response.status_code < 300:
                status = "delivered"
            else:
                all_ok = False
        except Exception as exc:
            response_body = str(exc)[:1000]
            all_ok = False

        delivery = WebhookDelivery(
            event_outbox_id=event.id,
            webhook_id=webhook.id,
            attempt=event.attempts + 1,
            status=status,
            response_code=response_code,
            response_body=response_body,
        )
        db.add(delivery)
        db.commit()

    return all_ok
