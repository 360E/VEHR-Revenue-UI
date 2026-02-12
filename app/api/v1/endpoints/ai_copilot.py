from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_membership, require_permission
from app.core.time import utc_now
from app.db.models.ai_message import AiMessage
from app.db.models.ai_thread import AiThread
from app.db.session import get_db
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
    entity_type: str | None = None
    entity_id: str | None = None
    quick_action: str | None = None


class AiChatRequest(BaseModel):
    thread_id: str | None = None
    message: str = Field(min_length=1, max_length=12000)
    context: AiChatContext


class AiChatResponse(BaseModel):
    thread: AiThreadSummaryRead
    assistant_message: AiMessageRead
    tool_results: dict[str, Any] = Field(default_factory=dict)
    fallback: bool = False


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

    try:
        assistant_content, meta = generate_copilot_response(
            db=db,
            organization_id=membership.organization_id,
            role=membership.role,
            message=message,
            context=context_payload,
            history=history,
        )
        user_content_encrypted = encrypt_sensitive_text(message)
        assistant_content_encrypted = encrypt_sensitive_text(assistant_content)
    except AiCopilotError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    user_message = AiMessage(thread_id=thread.id, role="user", content=user_content_encrypted)
    assistant_message = AiMessage(thread_id=thread.id, role="assistant", content=assistant_content_encrypted)
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

    tool_results = meta.get("tool_results") if isinstance(meta, dict) else None
    fallback = bool(meta.get("fallback")) if isinstance(meta, dict) else False

    log_event(
        db,
        action="ai_response_generated",
        entity_type="ai_thread",
        entity_id=thread.id,
        organization_id=membership.organization_id,
        actor=membership.user.email,
        metadata={
            "thread_id": thread.id,
            "assistant_message_id": assistant_message.id,
            "context_module": payload.context.module,
            "used_tools": sorted(list(tool_results.keys())) if isinstance(tool_results, dict) else [],
            "fallback": fallback,
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
        tool_results=tool_results if isinstance(tool_results, dict) else {},
        fallback=fallback,
    )
