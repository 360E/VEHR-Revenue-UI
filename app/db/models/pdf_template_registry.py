from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import uuid4

from sqlalchemy import Boolean, DateTime, Enum as PgEnum, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time import utc_now
from app.db.base import Base


class PdfDocumentKind(str, Enum):
    EOB = "EOB"
    REMITTANCE = "REMITTANCE"
    DENIAL = "DENIAL"
    UNKNOWN = "UNKNOWN"


class PdfTemplateRegistry(Base):
    __tablename__ = "pdf_template_registry"

    id: Mapped[str] = mapped_column(UUID(as_uuid=False), primary_key=True, default=lambda: str(uuid4()))
    payer_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    template_name: Mapped[str] = mapped_column(String(200), nullable=False)
    document_kind: Mapped[PdfDocumentKind] = mapped_column(
        PgEnum(PdfDocumentKind, name="pdf_document_kind"),
        nullable=False,
        default=PdfDocumentKind.UNKNOWN,
        index=True,
    )
    signature_version: Mapped[str] = mapped_column(String(50), nullable=False)
    signature_rules: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    anchor_hints: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    required_fields: Mapped[list | dict] = mapped_column(JSONB, nullable=False, default=list)
    confidence_thresholds: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
    )
