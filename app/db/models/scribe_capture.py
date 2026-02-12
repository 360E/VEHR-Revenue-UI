from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utc_now
from app.db.base import Base


class ScribeCapture(Base):
    __tablename__ = "scribe_captures"

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
    encounter_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("encounters.id"),
        nullable=False,
        index=True,
    )
    # Encrypted-at-rest payload using INTEGRATION_TOKEN_KEY.
    s3_key: Mapped[str] = mapped_column(String(500), nullable=False)
    duration_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True, index=True)

    organization: Mapped["Organization"] = relationship(
        "Organization",
        back_populates="scribe_captures",
    )
    user: Mapped["User"] = relationship(
        "User",
        back_populates="scribe_captures",
    )
    encounter: Mapped["Encounter"] = relationship(
        "Encounter",
        back_populates="scribe_captures",
    )
    transcripts: Mapped[list["ScribeTranscript"]] = relationship(
        "ScribeTranscript",
        back_populates="capture",
        cascade="all, delete-orphan",
    )
    drafts: Mapped[list["ScribeNoteDraft"]] = relationship(
        "ScribeNoteDraft",
        back_populates="capture",
        cascade="all, delete-orphan",
    )
