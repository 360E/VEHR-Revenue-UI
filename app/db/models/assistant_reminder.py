from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.db.base import Base


class AssistantReminder(Base):
    __tablename__ = "assistant_reminders"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    thread_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("ai_threads.id"), nullable=True, index=True)

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    channels: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="scheduled", index=True)

    repeat_mode: Mapped[str] = mapped_column(String(30), nullable=False, default="one_shot")
    nag_interval_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)
    fired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    msft_task_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    msft_event_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    msft_channel_status_json: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    msft_last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    msft_attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    msft_next_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
