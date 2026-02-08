from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.core.time import utc_now


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    organization_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("organizations.id"),
        nullable=True,
    )
    patient_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("patients.id"),
        nullable=True,
    )
    encounter_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("encounters.id"),
        nullable=True,
    )
    uploaded_by_user_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("users.id"),
        nullable=True,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    storage_provider: Mapped[str] = mapped_column(String(50), nullable=False, default="s3")
    storage_bucket: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    storage_region: Mapped[str | None] = mapped_column(String(50), nullable=True)
    storage_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now)

    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="documents",
    )
    patient: Mapped["Patient"] = relationship(
        "Patient",
        back_populates="documents",
    )
    encounter: Mapped["Encounter"] = relationship(
        "Encounter",
        back_populates="documents",
    )

