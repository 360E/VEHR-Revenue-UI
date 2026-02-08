from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.core.time import utc_now


class ReviewEvidenceLink(Base):
    __tablename__ = "review_evidence_links"
    __table_args__ = (
        UniqueConstraint("queue_item_id", "document_id", name="uq_review_evidence_queue_document"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    queue_item_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("review_queue_items.id"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("documents.id"),
        nullable=False,
    )
    created_by_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)

    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="review_evidence_links",
    )
    queue_item: Mapped["ReviewQueueItem"] = relationship(
        "ReviewQueueItem",
        back_populates="evidence_links",
    )
    created_by_user: Mapped["User | None"] = relationship(
        "User",
        back_populates="review_evidence_links",
    )

