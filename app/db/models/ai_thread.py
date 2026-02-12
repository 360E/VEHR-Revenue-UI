from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utc_now
from app.db.base import Base


class AiThread(Base):
    __tablename__ = "ai_threads"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "id",
            name="uq_ai_threads_org_id_id",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="ai_threads",
    )
    user: Mapped["User"] = relationship(
        "User",
        back_populates="ai_threads",
    )
    messages: Mapped[list["AiMessage"]] = relationship(
        "AiMessage",
        back_populates="thread",
        cascade="all, delete-orphan",
    )
