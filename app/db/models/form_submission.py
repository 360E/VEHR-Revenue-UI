from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class FormSubmission(Base):
    __tablename__ = "form_submissions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("organizations.id"),
        nullable=True,
    )
    patient_id: Mapped[str] = mapped_column(String(36), ForeignKey("patients.id"), nullable=False)
    encounter_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("encounters.id"),
        nullable=True,
    )
    form_template_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("form_templates.id"),
        nullable=False,
    )
    submitted_data_json: Mapped[str] = mapped_column(Text, nullable=False)
    pdf_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="form_submissions",
    )
    patient: Mapped["Patient"] = relationship(
        "Patient",
        back_populates="form_submissions",
    )
    encounter: Mapped["Encounter"] = relationship(
        "Encounter",
        back_populates="form_submissions",
    )
    form_template: Mapped["FormTemplate"] = relationship(
        "FormTemplate",
        back_populates="submissions",
    )
