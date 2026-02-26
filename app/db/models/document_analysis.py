from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import DateTime, Enum as PgEnum, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.db.base import Base


class DocumentType(str, Enum):
    ERA = "ERA"
    BILLED = "BILLED"


class DocumentAnalysis(Base):
    __tablename__ = "document_analyses"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    org_id: Mapped[str] = mapped_column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    job_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("recon_import_jobs.id"), nullable=True, index=True)
    document_type: Mapped[DocumentType] = mapped_column(PgEnum(DocumentType, name="document_type"), nullable=False, index=True)
    raw_json: Mapped[dict] = mapped_column(JSONB, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
