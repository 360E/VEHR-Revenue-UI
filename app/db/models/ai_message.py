from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utc_now
from app.db.base import Base


class AiMessage(Base):
    __tablename__ = "ai_messages"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    thread_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("ai_threads.id"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    # Encrypted-at-rest payload using INTEGRATION_TOKEN_KEY.
    content: Mapped[str] = mapped_column(Text, nullable=False)
    # Optional JSON metadata (agent_id, tool_calls, workstation_id, etc).
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now, index=True)

    thread: Mapped["AiThread"] = relationship(
        "AiThread",
        back_populates="messages",
    )
