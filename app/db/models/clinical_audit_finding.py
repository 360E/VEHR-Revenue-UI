from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.core.time import utc_now


class ClinicalAuditFinding(Base):
    __tablename__ = "clinical_audit_findings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    run_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("clinical_audit_runs.id"),
        nullable=False,
        index=True,
    )
    signal_type: Mapped[str] = mapped_column(String(80), nullable=False)
    subject_type: Mapped[str] = mapped_column(String(50), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(100), nullable=False)
    related_entities_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    finding_summary: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_references_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    suggested_correction: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)

    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="clinical_audit_findings",
    )
    run: Mapped["ClinicalAuditRun"] = relationship(
        "ClinicalAuditRun",
        back_populates="findings",
    )
    queue_items: Mapped[list["ReviewQueueItem"]] = relationship(
        "ReviewQueueItem",
        back_populates="source_finding",
    )

