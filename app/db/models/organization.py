from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Organization(Base):
    __tablename__ = "organizations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    patients: Mapped[list["Patient"]] = relationship(
        "Patient",
        back_populates="organization",
    )
    encounters: Mapped[list["Encounter"]] = relationship(
        "Encounter",
        back_populates="organization",
    )
    form_templates: Mapped[list["FormTemplate"]] = relationship(
        "FormTemplate",
        back_populates="organization",
    )
    form_submissions: Mapped[list["FormSubmission"]] = relationship(
        "FormSubmission",
        back_populates="organization",
    )
    documents: Mapped[list["Document"]] = relationship(
        "Document",
        back_populates="organization",
    )
    audit_events: Mapped[list["AuditEvent"]] = relationship(
        "AuditEvent",
        back_populates="organization",
    )
    outbox_events: Mapped[list["EventOutbox"]] = relationship(
        "EventOutbox",
        back_populates="organization",
    )
    webhooks: Mapped[list["WebhookEndpoint"]] = relationship(
        "WebhookEndpoint",
        back_populates="organization",
    )
    memberships: Mapped[list["OrganizationMembership"]] = relationship(
        "OrganizationMembership",
        back_populates="organization",
    )
