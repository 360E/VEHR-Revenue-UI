from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from app.db.models.pdf_template_registry import PdfTemplateRegistry
from app.services.pdf_extract_contract import (
    PdfExtractV1,
    PdfField,
    PdfLineItem,
    PdfMoneyField,
)


_DEFAULT_THRESHOLDS = {
    "fields": 0.72,
    "line_items": 0.72,
    "totals": 0.8,
    "overall": 0.75,
}
_TOLERANCE = Decimal("0.01")


@dataclass(frozen=True)
class ValidationResult:
    status: str
    failure_reasons: list[str]
    normalized_payload: dict[str, Any] | None


def _serialize_decimal(value: Decimal) -> str:
    return str(value.quantize(Decimal("0.01")))


def _normalize_code(raw: str) -> str:
    return (raw or "").strip().upper()


def _parse_iso_date(raw: str) -> str | None:
    candidate = (raw or "").strip()
    for fmt in ("%Y-%m-%d", "%m/%d/%Y", "%m/%d/%y"):
        try:
            return datetime.strptime(candidate, fmt).date().isoformat()
        except ValueError:
            continue
    return None


def _to_decimal(value: Any) -> Decimal:
    if isinstance(value, Decimal):
        return value
    cleaned = str(value).replace("$", "").replace(",", "").strip()
    try:
        return Decimal(cleaned)
    except (InvalidOperation, ValueError):
        raise ValueError("invalid currency")


class PdfExtractValidator:
    def __init__(self, default_thresholds: dict[str, float] | None = None) -> None:
        self._defaults = default_thresholds or _DEFAULT_THRESHOLDS

    def validate(self, extract: PdfExtractV1, template: PdfTemplateRegistry | None = None) -> ValidationResult:
        failures: list[str] = []
        thresholds = self._resolve_thresholds(template)
        anchor_hints = (template.anchor_hints if template else {}) or {}

        required_fields = (template.required_fields if template else []) or []
        self._validate_required_fields(extract, required_fields, thresholds, failures)

        totals = self._resolve_totals(extract, anchor_hints, failures)
        normalized_lines, line_sums = self._normalize_line_items(extract, thresholds, failures)

        normalized_totals = self._normalize_totals(totals, thresholds, failures, line_sums)
        self._cross_check(line_sums, normalized_totals, failures)

        if failures:
            return ValidationResult(status="FAIL", failure_reasons=failures, normalized_payload=None)

        normalized_fields = {
            name: {
                "value": field.value.strip(),
                "confidence": field.confidence,
                "provenance": field.provenance.model_dump(),
            }
            for name, field in extract.fields.items()
        }

        normalized_payload = {
            "extract_version": extract.extract_version,
            "engine": extract.engine,
            "engine_model_id": extract.engine_model_id,
            "engine_run_id": extract.engine_run_id,
            "generated_at": extract.generated_at.isoformat(),
            "source": extract.source.model_dump(),
            "fields": normalized_fields,
            "line_items": normalized_lines,
            "totals": normalized_totals,
            "warnings": list(extract.warnings),
            "raw_text_hashes": list(extract.raw_text_hashes),
        }
        return ValidationResult(status="PASS", failure_reasons=[], normalized_payload=normalized_payload)

    def _resolve_thresholds(self, template: PdfTemplateRegistry | None) -> dict[str, float]:
        thresholds = dict(self._defaults)
        if template and template.confidence_thresholds:
            for key, value in template.confidence_thresholds.items():
                try:
                    thresholds[key] = float(value)
                except (TypeError, ValueError):
                    continue
        return thresholds

    def _validate_required_fields(
        self,
        extract: PdfExtractV1,
        required_fields: list[str],
        thresholds: dict[str, float],
        failures: list[str],
    ) -> None:
        for field_name in required_fields:
            field = extract.fields.get(field_name)
            if not field:
                failures.append(f"missing required field: {field_name}")
                continue
            if field.confidence < thresholds["fields"]:
                failures.append(f"low confidence for field: {field_name}")

    def _resolve_totals(
        self,
        extract: PdfExtractV1,
        anchor_hints: dict,
        failures: list[str],
    ) -> dict[str, PdfMoneyField | None]:
        totals = {
            "billed_total": extract.totals.billed_total,
            "allowed_total": extract.totals.allowed_total,
            "paid_total": extract.totals.paid_total,
        }

        candidate_totals = extract.candidate_totals or {}
        if candidate_totals:
            total_hints = (anchor_hints.get("totals") or {}) if anchor_hints else {}
            for key, candidates in candidate_totals.items():
                if totals.get(key):
                    continue
                chosen = self._select_by_anchor(key, candidates, total_hints)
                if chosen:
                    totals[key] = chosen
                else:
                    failures.append(f"ambiguous totals for {key}")

        return totals

    def _select_by_anchor(
        self,
        key: str,
        candidates: list[PdfMoneyField],
        total_hints: dict[str, dict],
    ) -> PdfMoneyField | None:
        if not candidates:
            return None

        hints = total_hints.get(key, {})
        phrases = [p.lower() for p in hints.get("phrases", []) if isinstance(p, str)]
        preferred_hashes = [h.lower() for h in hints.get("snippet_hashes", []) if isinstance(h, str)]

        for preferred in preferred_hashes:
            for candidate in candidates:
                snippet = (candidate.provenance.snippet_hash or "").lower()
                if snippet == preferred:
                    return candidate

        if phrases:
            matches: list[PdfMoneyField] = []
            for phrase in phrases:
                for candidate in candidates:
                    anchor_text = (candidate.provenance.anchor_text or "").lower()
                    if phrase in anchor_text:
                        matches.append(candidate)
            if len(matches) == 1:
                return matches[0]
            if len(matches) > 1:
                return sorted(matches, key=lambda c: c.confidence, reverse=True)[0]

        if len(candidates) == 1:
            return candidates[0]
        return None

    def _normalize_line_items(
        self,
        extract: PdfExtractV1,
        thresholds: dict[str, float],
        failures: list[str],
    ) -> tuple[list[dict[str, Any]], dict[str, Decimal | None]]:
        normalized: list[dict[str, Any]] = []
        sum_billed: Decimal | None = None
        sum_allowed: Decimal | None = None
        sum_paid: Decimal | None = None

        for idx, line in enumerate(extract.line_items):
            try:
                normalized_line = self._normalize_line(line, thresholds)
            except ValueError as exc:
                failures.append(f"line {idx + 1}: {exc}")
                continue

            normalized.append(normalized_line)

            sum_billed = (sum_billed or Decimal("0")) + Decimal(normalized_line["billed_amount"])
            sum_allowed = (sum_allowed or Decimal("0")) + Decimal(normalized_line["allowed_amount"])
            sum_paid = (sum_paid or Decimal("0")) + Decimal(normalized_line["paid_amount"])

        return normalized, {
            "billed_total": sum_billed,
            "allowed_total": sum_allowed,
            "paid_total": sum_paid,
        }

    def _normalize_line(self, line: PdfLineItem, thresholds: dict[str, float]) -> dict[str, Any]:
        self._assert_confidence(line.billed_amount, thresholds["line_items"], "billed_amount")
        self._assert_confidence(line.allowed_amount, thresholds["line_items"], "allowed_amount")
        self._assert_confidence(line.paid_amount, thresholds["line_items"], "paid_amount")

        billed = _to_decimal(line.billed_amount.value)
        allowed = _to_decimal(line.allowed_amount.value)
        paid = _to_decimal(line.paid_amount.value)

        service_date_iso = _parse_iso_date(line.service_date.value)
        if not service_date_iso:
            raise ValueError("invalid service_date")
        code = _normalize_code(line.code.value)
        if not code:
            raise ValueError("missing code")

        adjustment_codes: list[str] = []
        for adj in line.adjustment_codes:
            if adj.confidence < thresholds["fields"]:
                continue
            normalized_adj = _normalize_code(adj.value)
            if normalized_adj:
                adjustment_codes.append(normalized_adj)

        return {
            "service_date": service_date_iso,
            "code": code,
            "billed_amount": _serialize_decimal(billed),
            "allowed_amount": _serialize_decimal(allowed),
            "paid_amount": _serialize_decimal(paid),
            "adjustment_codes": adjustment_codes,
        }

    def _assert_confidence(self, field: PdfField, threshold: float, name: str) -> None:
        if field.confidence < threshold:
            raise ValueError(f"low confidence for {name}")

    def _normalize_totals(
        self,
        totals: dict[str, PdfMoneyField | None],
        thresholds: dict[str, float],
        failures: list[str],
        line_sums: dict[str, Decimal | None],
    ) -> dict[str, str]:
        normalized: dict[str, str] = {}

        for key in ("billed_total", "allowed_total", "paid_total"):
            total_field = totals.get(key)
            if total_field:
                if total_field.confidence < thresholds["totals"]:
                    failures.append(f"low confidence for total: {key}")
                    continue
                try:
                    value = _to_decimal(total_field.value)
                    normalized[key] = _serialize_decimal(value)
                except ValueError:
                    failures.append(f"invalid currency for total: {key}")
            else:
                derived = line_sums.get(key)
                if derived is not None:
                    normalized[key] = _serialize_decimal(derived)
                else:
                    failures.append(f"missing total and no derivation available: {key}")

        return normalized

    def _cross_check(
        self,
        line_sums: dict[str, Decimal | None],
        totals: dict[str, str],
        failures: list[str],
    ) -> None:
        for key, sum_value in line_sums.items():
            total_raw = totals.get(key)
            if sum_value is None or total_raw is None:
                continue
            try:
                total_value = Decimal(total_raw)
            except (InvalidOperation, TypeError):
                failures.append(f"invalid normalized total for {key}")
                continue
            if abs(sum_value - total_value) > _TOLERANCE:
                failures.append(f"line-item sum mismatch for {key}")
