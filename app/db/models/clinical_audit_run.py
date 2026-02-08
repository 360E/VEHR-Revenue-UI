from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.core.time import utc_now


class ClinicalAuditRun(Base):
    __tablename__ = "clinical_audit_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organizations.id"),
        nullable=False,
        index=True,
    )
    triggered_by_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id"),
        nullable=True,
    )
    subject_type: Mapped[str] = mapped_column(String(50), nullable=False)
    subject_id: Mapped[str] = mapped_column(String(100), nullable=False)
    related_entities_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    mode: Mapped[str] = mapped_column(String(40), nullable=False, default="deterministic_only")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="started")
    started_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="clinical_audit_runs",
    )
    triggered_by_user: Mapped["User | None"] = relationship(
        "User",
        back_populates="triggered_clinical_audit_runs",
    )
    findings: Mapped[list["ClinicalAuditFinding"]] = relationship(
        "ClinicalAuditFinding",
        back_populates="run",
    )

