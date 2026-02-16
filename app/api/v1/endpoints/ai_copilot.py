from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_membership, get_current_membership_sse, require_permission
from app.core.time import utc_now
from app.db.models.ai_message import AiMessage
from app.db.models.ai_thread import AiThread
from app.db.models.assistant_memory_item import AssistantMemoryItem
from app.db.models.assistant_notification import AssistantNotification
from app.db.models.assistant_reminder import AssistantReminder
from app.db.session import get_db
from app.services.assistant.agent_registry import get_agent, list_agents_for_role
from app.services.assistant.enterprise_copilot import (
    EnterpriseAssistantError,
    build_reminder_summary,
    extract_reminder_due_at,
    generate_reply as generate_enterprise_reply,
    wants_reminder,
)
from app.services.assistant.msft_reminders import (
    channel_names as reminder_channel_names,
    ensure_msft_artifacts_for_reminder,
    select_reminder_channels,
)
from app.services.assistant.tool_gateway import execute_tool
from app.services.ai_copilot import (
    AiCopilotError,
    decrypt_sensitive_text,
    encrypt_sensitive_text,
    generate_copilot_response,
)
from app.services.audit import log_event


router = APIRouter(tags=["AI Copilot"])


class AiThreadCreateRequest(BaseModel):
    title: str | None = Field(default=None, max_length=120)


class AiMessageRead(BaseModel):
    id: str
    thread_id: str
    role: str
    content: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class AiThreadSummaryRead(BaseModel):
    id: str
    title: str | None = None
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime | None = None
    last_message_preview: str | None = None

    model_config = ConfigDict(from_attributes=True)


class AiChatContext(BaseModel):
    path: str
    module: str
    patient_id: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    quick_action: str | None = None


class AiChatRequest(BaseModel):
    agent_id: str | None = Field(default=None, max_length=80)
    thread_id: str | None = None
    message: str = Field(min_length=1, max_length=12000)
    context: AiChatContext
    workstation_id: str | None = Field(default=None, max_length=120)


class AiToolCallRead(BaseModel):
    tool_id: str
    status: str
    result: dict[str, Any] | None = None
    error: str | None = None


class AiChatResponse(BaseModel):
    thread: AiThreadSummaryRead
    assistant_message: AiMessageRead
    reply: str
    tool_calls: list[AiToolCallRead] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    tool_results: dict[str, Any] = Field(default_factory=dict)
    fallback: bool = False


class AgentRead(BaseModel):
    agent_id: str
    display_name: str


class AssistantMemoryItemRead(BaseModel):
    id: str
    key: str
    value: str
    tags: list[str] = Field(default_factory=list)
    source: str | None = None
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class AssistantMemoryUpsertRequest(BaseModel):
    key: str = Field(min_length=1, max_length=160)
    value: str = Field(min_length=1, max_length=4000)
    tags: list[str] = Field(default_factory=list)
    source: str | None = Field(default="user", max_length=80)
    expires_at: datetime | None = None


class AssistantReminderRead(BaseModel):
    id: str
    thread_id: str | None = None
    title: str
    body: str | None = None
    due_at: datetime
    channels: dict[str, Any] = Field(default_factory=dict)
    status: str
    repeat_mode: str
    nag_interval_minutes: int | None = None
    created_at: datetime
    fired_at: datetime | None = None
    msft_task_id: str | None = None
    msft_event_id: str | None = None
    msft_channel_status_json: dict[str, Any] = Field(default_factory=dict)
    msft_last_error: str | None = None
    msft_attempt_count: int = 0
    msft_next_attempt_at: datetime | None = None
    warnings: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class AssistantReminderCreateRequest(BaseModel):
    thread_id: str | None = None
    title: str = Field(min_length=1, max_length=255)
    body: str | None = Field(default=None, max_length=4000)
    due_at: datetime
    channels: dict[str, Any] = Field(default_factory=lambda: {"in_chat": True})
    repeat_mode: str = Field(default="one_shot", max_length=30)
    nag_interval_minutes: int | None = Field(default=None, ge=5, le=24 * 60)


class AssistantReminderUpdateRequest(BaseModel):
    status: str | None = Field(default=None, max_length=30)
    due_at: datetime | None = None
    nag_interval_minutes: int | None = Field(default=None, ge=5, le=24 * 60)


def _normalize_thread_title(raw_title: str | None, *, context: AiChatContext | None = None) -> str:
    title = (raw_title or "").strip()
    if title:
        return title[:120]

    module = (context.module if context else "").strip().replace("-", " ").replace("_", " ")
    if module:
        return f"{module.title()} Support"
    return "Staff Support"


def _message_read_from_row(row: AiMessage) -> AiMessageRead:
    try:
        content = decrypt_sensitive_text(row.content)
    except AiCopilotError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return AiMessageRead(
        id=row.id,
        thread_id=row.thread_id,
        role=row.role,
        content=content,
        created_at=row.created_at,
    )


def _thread_summary_from_row(db: Session, row: AiThread) -> AiThreadSummaryRead:
    latest = db.execute(
        select(AiMessage)
        .where(AiMessage.thread_id == row.id)
        .order_by(AiMessage.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    preview: str | None = None
    last_message_at: datetime | None = None
    if latest is not None:
        last_message_at = latest.created_at
        try:
            preview_content = decrypt_sensitive_text(latest.content)
            preview = preview_content.strip()[:180] or None
        except AiCopilotError:
            preview = "[Encrypted message]"

    return AiThreadSummaryRead(
        id=row.id,
        title=row.title,
        created_at=row.created_at,
        updated_at=row.updated_at,
        last_message_at=last_message_at,
        last_message_preview=preview,
    )


def _get_thread_or_404(*, db: Session, thread_id: str, organization_id: str, user_id: str) -> AiThread:
    thread = db.execute(
        select(AiThread).where(
            AiThread.id == thread_id,
            AiThread.organization_id == organization_id,
            AiThread.user_id == user_id,
        )
    ).scalar_one_or_none()
    if not thread:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Thread not found")
    return thread


def _sse_message(event: str, payload: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, default=str)}\n\n"


def _memory_item_allows_phi(*, key: str, tags: list[str]) -> bool:
    # Phase-1 guardrail: never persist PHI in memory by default.
    lowered_key = (key or "").strip().lower()
    lowered_tags = {str(tag).strip().lower() for tag in tags or []}

    if "phi" in lowered_tags or "patient" in lowered_tags:
        return False
    if any(token in lowered_key for token in ["patient", "mrn", "dob", "ssn", "diagnosis", "medication"]):
        return False
    return True


@router.get("/ai/threads", response_model=list[AiThreadSummaryRead])
def list_ai_threads(
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    membership=Depends(get_current_membership),
    _: None = Depends(require_permission("tasks:read_self")),
) -> list[AiThreadSummaryRead]:
    rows = db.execute(
        select(AiThread)
        .where(
            AiThread.organization_id == membership.organization_id,
            AiThread.user_id == membership.user_id,
        )
        .order_by(AiThread.updated_at.desc())
        .limit(limit)
    ).scalars().all()

    return [_thread_summary_from_row(db, row) for row in rows]


@router.get("/ai/agents", response_model=list[AgentRead])
def list_ai_agents(
    db: Session = Depends(get_db),
    membership=Depends(get_current_membership),
    _: None = Depends(require_permission("tasks:read_self")),
) -> list[AgentRead]:
    _ = db  # reserved for future agent registry persistence; keeps signature consistent with other endpoints.
    agents = [item for item in list_agents_for_role(membership.role) if item.agent_id != "legacy_copilot"]
    return [AgentRead(agent_id=item.agent_id, display_name=item.display_name) for item in agents]


@router.get("/ai/memory", response_model=list[AssistantMemoryItemRead])
def list_assistant_memory(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    membership=Depends(get_current_membership),
    _: None = Depends(require_permission("tasks:read_self")),
) -> list[AssistantMemoryItemRead]:
    rows = db.execute(
        select(AssistantMemoryItem)
        .where(
            AssistantMemoryItem.organization_id == membership.organization_id,
            AssistantMemoryItem.user_id == membership.user_id,
        )
        .order_by(AssistantMemoryItem.updated_at.desc())
        .limit(limit)
    ).scalars().all()
    return rows


@router.post("/ai/memory", response_model=AssistantMemoryItemRead, status_code=status.HTTP_201_CREATED)
def upsert_assistant_memory(
    payload: AssistantMemoryUpsertRequest,
    db: Session = Depends(get_db),
    membership=Depends(get_current_membership),
    _: None = Depends(require_permission("tasks:read_self")),
) -> AssistantMemoryItemRead:
    if not _memory_item_allows_phi(key=payload.key, tags=payload.tags):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="phi_memory_not_allowed")

    row = db.execute(
        select(AssistantMemoryItem).where(
            AssistantMemoryItem.organization_id == membership.organization_id,
            AssistantMemoryItem.user_id == membership.user_id,
            AssistantMemoryItem.key == payload.key,
        )
    ).scalar_one_or_none()

    if row is None:
        row = AssistantMemoryItem(
            organization_id=membership.organization_id,
            user_id=membership.user_id,
            key=payload.key,
            value=payload.value,
            tags=payload.tags,
            source=payload.source,
            expires_at=payload.expires_at,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
    else:
        row.value = payload.value
        row.tags = payload.tags
        row.source = payload.source
        row.expires_at = payload.expires_at
        row.updated_at = utc_now()
        db.add(row)
        db.commit()
        db.refresh(row)

    log_event(
        db,
        action="assistant_memory_set",
        entity_type="assistant_memory_item",
        entity_id=row.id,
        organization_id=membership.organization_id,
        actor=membership.user.email,
        metadata={"user_id": membership.user_id, "org_id": membership.organization_id, "key": row.key},
    )

    return row


@router.delete("/ai/memory", response_model=dict)
def delete_assistant_memory(
    memory_id: str = Query(..., alias="id"),
    db: Session = Depends(get_db),
    membership=Depends(get_current_membership),
    _: None = Depends(require_permission("tasks:read_self")),
) -> dict:
    row = db.get(AssistantMemoryItem, memory_id)
    if not row or row.organization_id != membership.organization_id or row.user_id != membership.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="memory_item_not_found")
    db.delete(row)
    db.commit()

    log_event(
        db,
        action="assistant_memory_deleted",
        entity_type="assistant_memory_item",
        entity_id=memory_id,
        organization_id=membership.organization_id,
        actor=membership.user.email,
        metadata={"user_id": membership.user_id, "org_id": membership.organization_id},
    )

    return {"ok": True}


@router.get("/ai/reminders", response_model=list[AssistantReminderRead])
def list_assistant_reminders(
    limit: int = Query(50, ge=1, le=200),
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    membership=Depends(get_current_membership),
    _: None = Depends(require_permission("tasks:read_self")),
) -> list[AssistantReminderRead]:
    query = select(AssistantReminder).where(
        AssistantReminder.organization_id == membership.organization_id,
        AssistantReminder.user_id == membership.user_id,
    )
    if status_filter:
        query = query.where(AssistantReminder.status == status_filter.strip())
    rows = db.execute(
        query.order_by(AssistantReminder.due_at.desc()).limit(limit)
    ).scalars().all()
    return rows


@router.post("/ai/reminders", response_model=AssistantReminderRead, status_code=status.HTTP_201_CREATED)
def create_assistant_reminder(
    payload: AssistantReminderCreateRequest,
    db: Session = Depends(get_db),
    membership=Depends(get_current_membership),
    _: None = Depends(require_permission("tasks:read_self")),
) -> AssistantReminderRead:
    selected_channels = select_reminder_channels(due_at=payload.due_at, raw_channels=payload.channels)
    reminder = AssistantReminder(
        organization_id=membership.organization_id,
        user_id=membership.user_id,
        thread_id=payload.thread_id,
        title=payload.title.strip()[:255],
        body=payload.body,
        due_at=payload.due_at,
        channels=selected_channels,
        status="scheduled",
        repeat_mode=payload.repeat_mode,
        nag_interval_minutes=payload.nag_interval_minutes,
    )
    db.add(reminder)
    db.commit()
    db.refresh(reminder)

    log_event(
        db,
        action="assistant_reminder_created",
        entity_type="assistant_reminder",
        entity_id=reminder.id,
        organization_id=membership.organization_id,
        actor=membership.user.email,
        metadata={
            "user_id": membership.user_id,
            "org_id": membership.organization_id,
            "thread_id": reminder.thread_id,
            "due_at": reminder.due_at.isoformat(),
            "channels": selected_channels,
            "repeat_mode": reminder.repeat_mode,
        },
    )

    agent = get_agent("enterprise_copilot")
    warnings: list[str] = []
    if agent is not None:
        warnings = ensure_msft_artifacts_for_reminder(
            db=db,
            tool_db=None,
            reminder=reminder,
            membership=membership,
            agent=agent,
            trigger="api",
        )
        db.refresh(reminder)

    response = AssistantReminderRead.model_validate(reminder, from_attributes=True)
    return response.model_copy(update={"warnings": warnings})


@router.patch("/ai/reminders/{reminder_id}", response_model=AssistantReminderRead)
def update_assistant_reminder(
    reminder_id: str,
    payload: AssistantReminderUpdateRequest,
    db: Session = Depends(get_db),
    membership=Depends(get_current_membership),
    _: None = Depends(require_permission("tasks:read_self")),
) -> AssistantReminderRead:
    reminder = db.get(AssistantReminder, reminder_id)
    if not reminder or reminder.organization_id != membership.organization_id or reminder.user_id != membership.user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="reminder_not_found")

    if payload.status is not None:
        normalized = payload.status.strip().lower()
        allowed = {"scheduled", "fired", "done", "canceled"}
        if normalized not in allowed:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="invalid_status")
        reminder.status = normalized
    if payload.due_at is not None:
        reminder.due_at = payload.due_at
    if payload.nag_interval_minutes is not None:
        reminder.nag_interval_minutes = payload.nag_interval_minutes
    db.add(reminder)
    db.commit()
    db.refresh(reminder)

    log_event(
        db,
        action="assistant_reminder_updated",
        entity_type="assistant_reminder",
        entity_id=reminder.id,
        organization_id=membership.organization_id,
        actor=membership.user.email,
        metadata={
            "user_id": membership.user_id,
            "org_id": membership.organization_id,
            "status": reminder.status,
            "due_at": reminder.due_at.isoformat(),
        },
    )

    return reminder


@router.get("/ai/notifications/stream")
async def stream_assistant_notifications(
    request: Request,
    membership=Depends(get_current_membership_sse),
    db: Session = Depends(get_db),
):
    auth_source = getattr(request.state, "sse_auth_source", None)
    if auth_source == "query_param":
        log_event(
            db,
            action="assistant_sse_query_token_used",
            entity_type="assistant_notifications_stream",
            entity_id=membership.user_id,
            organization_id=membership.organization_id,
            actor=membership.user.email,
            metadata={
                "user_id": membership.user_id,
                "org_id": membership.organization_id,
                "source": auth_source,
                "warning": "query_token_compat_enabled",
            },
        )

    async def event_generator():
        last_ping = utc_now()
        while True:
            if await request.is_disconnected():
                break

            rows = db.execute(
                select(AssistantNotification)
                .where(
                    AssistantNotification.organization_id == membership.organization_id,
                    AssistantNotification.user_id == membership.user_id,
                    AssistantNotification.delivered_at.is_(None),
                )
                .order_by(AssistantNotification.created_at.asc())
                .limit(25)
            ).scalars().all()

            if rows:
                for row in rows:
                    yield _sse_message(
                        "notification",
                        {
                            "id": row.id,
                            "type": row.type,
                            "title": row.title,
                            "body": row.body,
                            "reminder_id": row.reminder_id,
                            "channel": row.channel,
                            "due_at": row.due_at,
                            "created_at": row.created_at,
                        },
                    )
                    row.delivered_at = utc_now()
                    db.add(row)
                    try:
                        db.commit()
                    except Exception:
                        db.rollback()
            else:
                await asyncio.sleep(2.0)

            now = utc_now()
            if now - last_ping >= timedelta(seconds=15):
                last_ping = now
                yield ": ping\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/ai/threads", response_model=AiThreadSummaryRead, status_code=status.HTTP_201_CREATED)
def create_ai_thread(
    payload: AiThreadCreateRequest,
    db: Session = Depends(get_db),
    membership=Depends(get_current_membership),
    _: None = Depends(require_permission("tasks:read_self")),
) -> AiThreadSummaryRead:
    title = _normalize_thread_title(payload.title)
    thread = AiThread(
        organization_id=membership.organization_id,
        user_id=membership.user_id,
        title=title,
    )
    db.add(thread)
    db.commit()
    db.refresh(thread)

    log_event(
        db,
        action="ai_thread_created",
        entity_type="ai_thread",
        entity_id=thread.id,
        organization_id=membership.organization_id,
        actor=membership.user.email,
        metadata={"thread_id": thread.id},
    )

    return _thread_summary_from_row(db, thread)


@router.get("/ai/threads/{thread_id}/messages", response_model=list[AiMessageRead])
def list_ai_thread_messages(
    thread_id: str,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db),
    membership=Depends(get_current_membership),
    _: None = Depends(require_permission("tasks:read_self")),
) -> list[AiMessageRead]:
    thread = _get_thread_or_404(
        db=db,
        thread_id=thread_id,
        organization_id=membership.organization_id,
        user_id=membership.user_id,
    )

    rows = db.execute(
        select(AiMessage)
        .where(AiMessage.thread_id == thread.id)
        .order_by(AiMessage.created_at.desc())
        .limit(limit)
    ).scalars().all()
    rows.reverse()

    return [_message_read_from_row(row) for row in rows]


@router.post("/ai/chat", response_model=AiChatResponse)
def chat_with_copilot(
    payload: AiChatRequest,
    db: Session = Depends(get_db),
    membership=Depends(get_current_membership),
    _: None = Depends(require_permission("tasks:read_self")),
) -> AiChatResponse:
    message = payload.message.strip()
    if not message:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="message is required")

    agent_id = (payload.agent_id or "enterprise_copilot").strip()
    agent = get_agent(agent_id)
    if agent is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="unknown_agent")
    if not agent.role_allowed(membership.role):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="agent_not_allowed_for_role")

    created_new_thread = False
    if payload.thread_id:
        thread = _get_thread_or_404(
            db=db,
            thread_id=payload.thread_id,
            organization_id=membership.organization_id,
            user_id=membership.user_id,
        )
    else:
        thread = AiThread(
            organization_id=membership.organization_id,
            user_id=membership.user_id,
            title=_normalize_thread_title(None, context=payload.context),
        )
        db.add(thread)
        db.flush()
        created_new_thread = True

    history_rows = db.execute(
        select(AiMessage)
        .where(AiMessage.thread_id == thread.id)
        .order_by(AiMessage.created_at.desc())
        .limit(20)
    ).scalars().all()
    history_rows.reverse()

    history: list[dict[str, str]] = []
    for row in history_rows:
        role = (row.role or "").strip().lower()
        if role not in {"user", "assistant"}:
            continue
        try:
            content = decrypt_sensitive_text(row.content)
        except AiCopilotError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
        history.append({"role": role, "content": content})

    context_payload = payload.context.model_dump(exclude_none=True)
    patient_id = payload.context.patient_id
    workstation_id = payload.workstation_id

    memory_rows = db.execute(
        select(AssistantMemoryItem)
        .where(
            AssistantMemoryItem.organization_id == membership.organization_id,
            AssistantMemoryItem.user_id == membership.user_id,
        )
        .order_by(AssistantMemoryItem.updated_at.desc())
        .limit(50)
    ).scalars().all()
    memory_items = [
        {"key": row.key, "value": row.value, "tags": row.tags, "source": row.source}
        for row in memory_rows
        if row.expires_at is None or row.expires_at > utc_now()
    ]

    log_event(
        db,
        action="assistant_chat_received",
        entity_type="ai_thread",
        entity_id=thread.id,
        organization_id=membership.organization_id,
        patient_id=patient_id,
        actor=membership.user.email,
        metadata={
            "user_id": membership.user_id,
            "org_id": membership.organization_id,
            "role": membership.role,
            "agent_id": agent.agent_id,
            "thread_id": thread.id,
            "message": message,
            "context": context_payload,
            "workstation_id": workstation_id,
        },
    )

    tool_calls: list[AiToolCallRead] = []
    warnings: list[str] = []

    try:
        tool_results: dict[str, Any] = {}
        fallback = False

        if agent.agent_id == "legacy_copilot":
            assistant_content, meta = generate_copilot_response(
                db=db,
                organization_id=membership.organization_id,
                role=membership.role,
                message=message,
                context=context_payload,
                history=history,
            )
            tool_results = meta.get("tool_results") if isinstance(meta, dict) else {}
            fallback = bool(meta.get("fallback")) if isinstance(meta, dict) else False
        else:
            if wants_reminder(message):
                now = utc_now()
                due_at = extract_reminder_due_at(message, now=now)
                if due_at is None:
                    assistant_content = (
                        "I can create a reminder, but I need a specific time window.\n"
                        "Examples: 'tomorrow at 3pm', 'in 30 minutes', or 'next week'."
                    )
                    warnings.append("reminder_time_missing")
                    fallback = True
                else:
                    selected_channels = select_reminder_channels(due_at=due_at, raw_channels=None, message=message)

                    def _create_reminder() -> dict[str, Any]:
                        reminder = AssistantReminder(
                            organization_id=membership.organization_id,
                            user_id=membership.user_id,
                            thread_id=thread.id,
                            title=message.strip()[:255],
                            body=None,
                            due_at=due_at,
                            channels=selected_channels,
                            status="scheduled",
                            repeat_mode="one_shot",
                            nag_interval_minutes=None,
                        )
                        db.add(reminder)
                        db.commit()
                        db.refresh(reminder)
                        log_event(
                            db,
                            action="assistant_reminder_created",
                            entity_type="assistant_reminder",
                            entity_id=reminder.id,
                            organization_id=membership.organization_id,
                            patient_id=patient_id,
                            actor=membership.user.email,
                            metadata={
                                "user_id": membership.user_id,
                                "org_id": membership.organization_id,
                                "thread_id": thread.id,
                                "agent_id": agent.agent_id,
                                "due_at": reminder.due_at.isoformat(),
                                "channels": reminder.channels,
                                "workstation_id": workstation_id,
                            },
                        )
                        msft_warnings = ensure_msft_artifacts_for_reminder(
                            db=db,
                            tool_db=None,
                            reminder=reminder,
                            membership=membership,
                            agent=agent,
                            trigger="chat",
                            patient_id=patient_id,
                            workstation_id=workstation_id,
                        )
                        db.refresh(reminder)
                        return {
                            "reminder_id": reminder.id,
                            "due_at": reminder.due_at.isoformat(),
                            "channels": reminder.channels,
                            "msft_task_id": reminder.msft_task_id,
                            "msft_event_id": reminder.msft_event_id,
                            "warnings": msft_warnings,
                        }

                    tool_result = execute_tool(
                        db=db,
                        membership=membership,
                        agent=agent,
                        tool_id="reminder.create",
                        args={"message": message, "due_at": due_at.isoformat(), "channels": selected_channels},
                        patient_id=patient_id,
                        workstation_id=workstation_id,
                        executor=_create_reminder,
                    )
                    tool_calls.append(
                        AiToolCallRead(
                            tool_id=tool_result.tool_id,
                            status=tool_result.status,
                            result=tool_result.result,
                            error=tool_result.error,
                        )
                    )
                    if tool_result.status in {"blocked", "error"}:
                        assistant_content = (
                            "I couldn't create that reminder due to policy restrictions. "
                            "Try providing a specific time and avoid PHI."
                        )
                        warnings.append(tool_result.error or "reminder_blocked")
                        fallback = True
                    else:
                        result_warnings = []
                        if tool_result.result and isinstance(tool_result.result.get("warnings"), list):
                            result_warnings = [str(item) for item in tool_result.result.get("warnings") if str(item).strip()]
                        warnings.extend(result_warnings)
                        assistant_content = build_reminder_summary(
                            title=message.strip()[:255],
                            due_at=due_at,
                            channels=reminder_channel_names(selected_channels),
                            repeat_mode="one_shot",
                        )
                        fallback = True
            else:
                assistant_content, meta = generate_enterprise_reply(
                    role=membership.role,
                    message=message,
                    context=context_payload,
                    history=history,
                    memory_items=memory_items,
                    actions_allowed=set(agent.actions_allowed),
                )
                fallback = bool(meta.get("fallback")) if isinstance(meta, dict) else False
                if isinstance(meta, dict):
                    warnings.extend(meta.get("warnings") or [])

        user_content_encrypted = encrypt_sensitive_text(message)
        assistant_content_encrypted = encrypt_sensitive_text(assistant_content)
    except AiCopilotError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except EnterpriseAssistantError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    metadata_json = json.dumps(
        {
            "agent_id": agent.agent_id,
            "patient_id": patient_id,
            "workstation_id": workstation_id,
            "tool_calls": [item.model_dump(exclude_none=True) for item in tool_calls],
            "warnings": warnings,
        },
        default=str,
    )
    user_message = AiMessage(
        thread_id=thread.id,
        role="user",
        content=user_content_encrypted,
        metadata_json=metadata_json,
    )
    assistant_message = AiMessage(
        thread_id=thread.id,
        role="assistant",
        content=assistant_content_encrypted,
        metadata_json=metadata_json,
    )
    thread.updated_at = utc_now()

    db.add(user_message)
    db.add(assistant_message)
    db.add(thread)
    db.commit()
    db.refresh(thread)
    db.refresh(assistant_message)

    if created_new_thread:
        log_event(
            db,
            action="ai_thread_created",
            entity_type="ai_thread",
            entity_id=thread.id,
            organization_id=membership.organization_id,
            actor=membership.user.email,
            metadata={"thread_id": thread.id, "created_via": "chat"},
        )

    log_event(
        db,
        action="assistant_chat_replied",
        entity_type="ai_thread",
        entity_id=thread.id,
        organization_id=membership.organization_id,
        patient_id=patient_id,
        actor=membership.user.email,
        metadata={
            "user_id": membership.user_id,
            "org_id": membership.organization_id,
            "role": membership.role,
            "agent_id": agent.agent_id,
            "thread_id": thread.id,
            "assistant_message_id": assistant_message.id,
            "context_module": payload.context.module,
            "tool_calls": [item.model_dump(exclude_none=True) for item in tool_calls],
            "warnings": warnings,
            "fallback": fallback,
            "workstation_id": workstation_id,
        },
    )

    return AiChatResponse(
        thread=_thread_summary_from_row(db, thread),
        assistant_message=AiMessageRead(
            id=assistant_message.id,
            thread_id=assistant_message.thread_id,
            role=assistant_message.role,
            content=assistant_content,
            created_at=assistant_message.created_at,
        ),
        reply=assistant_content,
        tool_calls=tool_calls,
        warnings=warnings,
        tool_results=tool_results if isinstance(tool_results, dict) else {},
        fallback=fallback,
    )
