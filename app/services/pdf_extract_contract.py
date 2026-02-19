from __future__ import annotations

import hashlib
from datetime import datetime
from decimal import Decimal, InvalidOperation
from enum import Enum
from typing import Any, Dict, List, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _sha256_hexdigest(raw: str | bytes) -> str:
    data = raw if isinstance(raw, (bytes, bytearray)) else raw.encode("utf-8")
    return hashlib.sha256(data).hexdigest()


class DocumentTypeGuess(str, Enum):
    EOB = "EOB"
    REMITTANCE = "REMITTANCE"
    DENIAL = "DENIAL"
    UNKNOWN = "UNKNOWN"


class PdfFieldProvenance(BaseModel):
    page_number: int
    bounding_box: list[float] = Field(default_factory=list)
    snippet_hash: str
    anchor_text: str | None = None

    model_config = ConfigDict(frozen=True)

    @field_validator("page_number")
    @classmethod
    def _positive_page(cls, value: int) -> int:
        if value < 1:
            raise ValueError("page_number must be >= 1")
        return value


class PdfField(BaseModel):
    value: str
    confidence: float
    provenance: PdfFieldProvenance

    model_config = ConfigDict(frozen=True)

    @field_validator("confidence")
    @classmethod
    def _validate_confidence(cls, value: float) -> float:
        if not 0 <= float(value) <= 1:
            raise ValueError("confidence must be between 0 and 1")
        return float(value)


class PdfMoneyField(PdfField):
    value: Decimal

    @field_validator("value", mode="before")
    @classmethod
    def _as_decimal(cls, value: Any) -> Decimal:
        if isinstance(value, Decimal):
            return value
        try:
            cleaned = str(value).replace("$", "").replace(",", "").strip()
            return Decimal(cleaned)
        except (InvalidOperation, ValueError, TypeError):
            raise ValueError("invalid currency value")


class PdfLineItem(BaseModel):
    service_date: PdfField
    code: PdfField
    billed_amount: PdfMoneyField
    allowed_amount: PdfMoneyField
    paid_amount: PdfMoneyField
    adjustment_codes: list[PdfField] = Field(default_factory=list)

    model_config = ConfigDict(frozen=True)


class PdfTotals(BaseModel):
    billed_total: PdfMoneyField | None = None
    allowed_total: PdfMoneyField | None = None
    paid_total: PdfMoneyField | None = None

    model_config = ConfigDict(frozen=True)


class PdfExtractSource(BaseModel):
    file_name: str
    file_sha256: str
    page_count: int
    document_type_guess: DocumentTypeGuess
    template_id: str | None = None
    template_confidence: float | None = None
    signature_version: str | None = None
    raw_pdf_uri: str | None = None

    model_config = ConfigDict(frozen=True)

    @field_validator("page_count")
    @classmethod
    def _validate_pages(cls, value: int) -> int:
        if value < 1:
            raise ValueError("page_count must be >= 1")
        return value

    @field_validator("template_confidence")
    @classmethod
    def _validate_template_conf(cls, value: float | None) -> float | None:
        if value is None:
            return None
        if not 0 <= float(value) <= 1:
            raise ValueError("template_confidence must be between 0 and 1")
        return float(value)


class PdfExtractV1(BaseModel):
    extract_version: str
    engine: str
    engine_model_id: str | None = None
    engine_run_id: str | None = None
    generated_at: datetime
    source: PdfExtractSource
    fields: dict[str, PdfField] = Field(default_factory=dict)
    line_items: list[PdfLineItem] = Field(default_factory=list)
    totals: PdfTotals = Field(default_factory=PdfTotals)
    candidate_totals: dict[str, list[PdfMoneyField]] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    raw_text_hashes: list[str] = Field(default_factory=list)

    model_config = ConfigDict(
        frozen=True,
        extra="ignore",
        json_encoders={Decimal: lambda v: str(v)},
    )

    @field_validator("engine")
    @classmethod
    def _engine_lower(cls, value: str) -> str:
        if not value:
            raise ValueError("engine is required")
        return value.strip()

    @field_validator("raw_text_hashes")
    @classmethod
    def _dedupe_hashes(cls, hashes: Sequence[str]) -> list[str]:
        seen: set[str] = set()
        ordered: list[str] = []
        for h in hashes:
            if not h:
                continue
            if h not in seen:
                seen.add(h)
                ordered.append(h)
        return ordered


def compute_snippet_hash(snippet: str) -> str:
    return _sha256_hexdigest(snippet or "")


def compute_raw_text_hashes(texts: Sequence[str]) -> list[str]:
    return [compute_snippet_hash(text) for text in texts if text]


def attach_template_metadata(
    extract: PdfExtractV1,
    template_id: str | None,
    template_confidence: float | None,
    signature_version: str | None,
) -> PdfExtractV1:
    updated_source = extract.source.model_copy(
        update={
            "template_id": template_id,
            "template_confidence": template_confidence,
            "signature_version": signature_version,
        }
    )
    return extract.model_copy(update={"source": updated_source})
