from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.time import utc_now
from app.db.base import Base


class ScribeTranscript(Base):
    __tablename__ = "scribe_transcripts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    capture_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("scribe_captures.id"),
        nullable=False,
        index=True,
    )
    # Encrypted-at-rest payload using INTEGRATION_TOKEN_KEY.
    text: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utc_now, index=True)

    capture: Mapped["ScribeCapture"] = relationship(
        "ScribeCapture",
        back_populates="transcripts",
    )
