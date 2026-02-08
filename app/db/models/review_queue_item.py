from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.core.time import utc_now


class ReviewQueueItem(Base):
    __tablename__ = "review_queue_items"
    __table_args__ = (
        UniqueConstraint("source_finding_id", name="uq_review_queue_source_finding"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    subject_type: Mapped[str] = mapped_column(String(50), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(100), nullable=False)
    source_finding_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("clinical_audit_findings.id"),
        nullable=True,
    )
    reason_code: Mapped[str] = mapped_column(String(100), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="open")
    assigned_to_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id"),
        nullable=True,
    )
    due_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)

    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="review_queue_items",
    )
    assigned_to_user: Mapped["User | None"] = relationship(
        "User",
        back_populates="assigned_review_queue_items",
    )
    source_finding: Mapped["ClinicalAuditFinding | None"] = relationship(
        "ClinicalAuditFinding",
        back_populates="queue_items",
    )
    actions: Mapped[list["ReviewAction"]] = relationship(
        "ReviewAction",
        back_populates="queue_item",
    )
    evidence_links: Mapped[list["ReviewEvidenceLink"]] = relationship(
        "ReviewEvidenceLink",
        back_populates="queue_item",
    )

