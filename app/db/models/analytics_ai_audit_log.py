from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.db.base import Base


class AnalyticsAiAuditLog(Base):
    __tablename__ = "analytics_ai_audit_logs"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    membership_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)

    report_key: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    conversation_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)
    message_id: Mapped[str] = mapped_column(UUID(as_uuid=False), nullable=False, index=True)

    user_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[str] = mapped_column(String(80), nullable=False, default="dashboard_question")
    rationale: Mapped[str] = mapped_column(Text, nullable=False)

    metrics_used: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    filters_applied: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    query_requests: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    query_responses_summary: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now, index=True)

