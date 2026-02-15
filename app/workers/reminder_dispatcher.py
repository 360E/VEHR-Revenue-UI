from __future__ import annotations

import json
import logging
import time
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.db.models.ai_message import AiMessage
from app.db.models.ai_thread import AiThread
from app.db.models.assistant_notification import AssistantNotification
from app.db.models.assistant_reminder import AssistantReminder
from app.db.session import SessionLocal
from app.services.ai_copilot import AiCopilotError, encrypt_sensitive_text
from app.services.audit import log_event


logger = logging.getLogger(__name__)

# Fixed poll interval for Phase-1 (avoid introducing new env vars).
POLL_SECONDS = 30
CLAIM_LIMIT = 25


def dispatch_due_reminders(db: Session, *, limit: int = CLAIM_LIMIT) -> int:
    now = utc_now()
    query = (
        select(AssistantReminder)
        .where(
            AssistantReminder.status == "scheduled",
            AssistantReminder.due_at <= now,
        )
        .order_by(AssistantReminder.due_at.asc())
        .limit(limit)
    )
    # Postgres: use SKIP LOCKED to avoid double-fire with multiple workers.
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        query = query.with_for_update(skip_locked=True)

    rows = db.execute(query).scalars().all()
    fired = 0

    for reminder in rows:
        channel = "in_chat"
        due_at = reminder.due_at
        delivery_targets = {"in_chat": True}

        notification = AssistantNotification(
            organization_id=reminder.organization_id,
            user_id=reminder.user_id,
            reminder_id=reminder.id,
            type="reminder",
            title=reminder.title,
            body=reminder.body,
            channel=channel,
            due_at=due_at,
            attempt=0,
            delivery_targets=delivery_targets,
        )

        try:
            db.add(notification)

            # Persist an in-chat assistant message when a thread is known so history survives reloads.
            if reminder.thread_id:
                thread = db.execute(
                    select(AiThread).where(
                        AiThread.id == reminder.thread_id,
                        AiThread.organization_id == reminder.organization_id,
                        AiThread.user_id == reminder.user_id,
                    )
                ).scalar_one_or_none()
                if thread is not None:
                    try:
                        plaintext = f"Reminder: {reminder.title}".strip()
                        if reminder.body:
                            plaintext = f"{plaintext}\n{reminder.body}".strip()
                        encrypted = encrypt_sensitive_text(plaintext)
                        db.add(
                            AiMessage(
                                thread_id=thread.id,
                                role="assistant",
                                content=encrypted,
                                metadata_json=json.dumps(
                                    {
                                        "type": "assistant_notification",
                                        "notification_id": notification.id,
                                        "reminder_id": reminder.id,
                                        "channel": channel,
                                        "due_at": due_at.isoformat(),
                                    },
                                    default=str,
                                ),
                            )
                        )
                    except AiCopilotError:
                        # Notification record will still deliver the reminder even if message encryption fails.
                        logger.exception("reminder_dispatcher_encrypt_failed reminder_id=%s", reminder.id)

            # Mark reminder as fired or reschedule (nag mode).
            reminder.fired_at = now
            if reminder.repeat_mode == "nag_until_done" and reminder.status not in {"done", "canceled"}:
                interval = reminder.nag_interval_minutes or 60
                reminder.due_at = now + timedelta(minutes=interval)
                reminder.status = "scheduled"
            else:
                reminder.status = "fired"

            db.add(reminder)
            db.commit()
            fired += 1

            log_event(
                db,
                action="assistant_reminder_fired",
                entity_type="assistant_reminder",
                entity_id=reminder.id,
                organization_id=reminder.organization_id,
                actor=None,
                metadata={
                    "user_id": reminder.user_id,
                    "org_id": reminder.organization_id,
                    "due_at": due_at.isoformat(),
                    "channel": channel,
                    "notification_id": notification.id,
                },
            )
        except IntegrityError:
            # Idempotency: notification already exists for this due_at/channel/attempt.
            db.rollback()
            try:
                reminder.fired_at = now
                reminder.status = "fired"
                db.add(reminder)
                db.commit()
            except Exception:
                db.rollback()
                logger.exception("reminder_dispatcher_failed_to_mark_fired reminder_id=%s", reminder.id)
        except Exception:
            db.rollback()
            logger.exception("reminder_dispatcher_failed reminder_id=%s", reminder.id)

    return fired


def run_loop() -> None:
    logger.info("assistant_reminder_dispatcher_start poll_seconds=%s", POLL_SECONDS)
    while True:
        db = SessionLocal()
        try:
            fired = dispatch_due_reminders(db)
            if fired:
                logger.info("assistant_reminder_dispatcher_fired count=%s", fired)
        except Exception:
            logger.exception("assistant_reminder_dispatcher_loop_error")
        finally:
            db.close()

        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_loop()
