from datetime import datetime
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utc_now
from app.db.base import Base


class ScribeNoteDraft(Base):
    __tablename__ = "scribe_note_drafts"
    __table_args__ = (
        CheckConstraint(
            "note_type in ('SOAP','DAP')",
            name="ck_scribe_note_drafts_note_type",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    capture_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("scribe_captures.id"),
        nullable=False,
        index=True,
    )
    note_type: Mapped[str] = mapped_column(String(10), nullable=False, index=True)
    # Encrypted-at-rest payload using INTEGRATION_TOKEN_KEY.
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now, onupdate=utc_now)

    capture: Mapped["ScribeCapture"] = relationship(
        "ScribeCapture",
        back_populates="drafts",
    )
