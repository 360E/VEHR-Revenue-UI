from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from app.db.models.pdf_template_registry import PdfDocumentKind, PdfTemplateRegistry
from app.services.pdf_extract_contract import (
    DocumentTypeGuess,
    PdfExtractSource,
    PdfExtractV1,
    PdfField,
    PdfFieldProvenance,
    PdfLineItem,
    PdfMoneyField,
    PdfTotals,
    attach_template_metadata,
    compute_raw_text_hashes,
)
from app.services.pdf_extract_validator import PdfExtractValidator
from app.services.pdf_template_classifier import PdfSignatureSnapshot, PdfTemplateClassifier


def _prov(anchor: str | None = None) -> PdfFieldProvenance:
    return PdfFieldProvenance(page_number=1, bounding_box=[0.0, 0.0, 1.0, 1.0], snippet_hash="hash", anchor_text=anchor)


def _field(value: str, confidence: float = 0.9) -> PdfField:
    return PdfField(value=value, confidence=confidence, provenance=_prov())


def _money(value: str | Decimal, confidence: float = 0.9, anchor: str | None = None) -> PdfMoneyField:
    return PdfMoneyField(value=value, confidence=confidence, provenance=_prov(anchor))


def _sample_extract(
    line_items: list[PdfLineItem],
    totals: PdfTotals,
    candidate_totals: dict[str, list[PdfMoneyField]] | None = None,
    template_id: str | None = None,
    template_confidence: float | None = None,
    signature_version: str | None = None,
) -> PdfExtractV1:
    source = PdfExtractSource(
        file_name="demo.pdf",
        file_sha256="deadbeef",
        page_count=1,
        document_type_guess=DocumentTypeGuess.EOB,
        template_id=template_id,
        template_confidence=template_confidence,
        signature_version=signature_version,
    )
    return PdfExtractV1(
        extract_version="1.0",
        engine="azure_document_intelligence",
        engine_model_id="prebuilt-layout",
        engine_run_id="run-123",
        generated_at=datetime(2026, 2, 19, 0, 0, 0),
        source=source,
        fields={"member_id": _field("ABC123")},
        line_items=line_items,
        totals=totals,
        candidate_totals=candidate_totals or {},
        warnings=[],
        raw_text_hashes=compute_raw_text_hashes(["demo"]),
    )


def test_template_classifier_is_deterministic_for_same_pdf() -> None:
    classifier = PdfTemplateClassifier()
    template = PdfTemplateRegistry(
        id="tpl-1",
        payer_id="payer-1",
        template_name="Acme EOB",
        document_kind=PdfDocumentKind.EOB,
        signature_version="sig-v1",
        signature_rules=[
            {"type": "contains_phrase", "phrase": "acme health plan"},
            {"type": "page_heading_match", "heading": "explanation of benefits"},
        ],
        anchor_hints={},
        required_fields=[],
        confidence_thresholds={"overall": 0.5},
        active=True,
    )
    competing = PdfTemplateRegistry(
        id="tpl-2",
        payer_id="payer-1",
        template_name="Other",
        document_kind=PdfDocumentKind.EOB,
        signature_version="sig-v1",
        signature_rules=[{"type": "contains_phrase", "phrase": "other payer"}],
        anchor_hints={},
        required_fields=[],
        confidence_thresholds={"overall": 0.5},
        active=True,
    )
    snapshot = PdfSignatureSnapshot(
        full_text="ACME HEALTH PLAN Explanation of Benefits for member",
        page_headings=["Explanation of Benefits"],
        table_headers=[],
        document_kind=DocumentTypeGuess.EOB,
        payer_id="payer-1",
    )

    first = classifier.classify(snapshot, [template, competing])
    second = classifier.classify(snapshot, [template, competing])

    assert first is not None
    assert second is not None
    assert first.template_id == second.template_id == "tpl-1"
    assert first.signature_version == "sig-v1"


def test_validator_fails_on_ambiguous_totals_without_anchors() -> None:
    line = PdfLineItem(
        service_date=_field("01/01/2026"),
        code=_field("99213"),
        billed_amount=_money("100.00"),
        allowed_amount=_money("80.00"),
        paid_amount=_money("80.00"),
        adjustment_codes=[],
    )
    candidate_totals = {
        "paid_total": [
            _money("80.00", anchor="net amount"),
            _money("60.00", anchor="payment"),
        ]
    }
    extract = _sample_extract(line_items=[line], totals=PdfTotals(), candidate_totals=candidate_totals)
    validator = PdfExtractValidator()

    result = validator.validate(extract)

    assert result.status == "FAIL"
    assert any("ambiguous totals" in reason for reason in result.failure_reasons)


def test_validator_low_confidence_totals_fail() -> None:
    line = PdfLineItem(
        service_date=_field("01/01/2026"),
        code=_field("99213"),
        billed_amount=_money("100.00"),
        allowed_amount=_money("80.00"),
        paid_amount=_money("80.00"),
        adjustment_codes=[],
    )
    totals = PdfTotals(
        billed_total=_money("100.00", confidence=0.2),
        allowed_total=_money("80.00", confidence=0.2),
        paid_total=_money("80.00", confidence=0.2),
    )
    extract = _sample_extract(line_items=[line], totals=totals)
    validator = PdfExtractValidator()

    result = validator.validate(extract)

    assert result.status == "FAIL"
    assert any("low confidence for total" in reason for reason in result.failure_reasons)


def test_validator_rejects_malformed_decimal_values() -> None:
    bad_money = PdfMoneyField.model_construct(value="12.xx", confidence=0.9, provenance=_prov())
    line = PdfLineItem(
        service_date=_field("01/01/2026"),
        code=_field("99213"),
        billed_amount=bad_money,
        allowed_amount=_money("10.00"),
        paid_amount=_money("10.00"),
        adjustment_codes=[],
    )
    totals = PdfTotals(
        billed_total=_money("10.00"),
        allowed_total=_money("10.00"),
        paid_total=_money("10.00"),
    )
    extract = _sample_extract(line_items=[line], totals=totals)
    validator = PdfExtractValidator()

    result = validator.validate(extract)

    assert result.status == "FAIL"
    assert any("invalid currency" in reason for reason in result.failure_reasons)


def test_template_version_recorded_in_extract_and_normalized_payload() -> None:
    classifier = PdfTemplateClassifier()
    template = PdfTemplateRegistry(
        id="tpl-10",
        payer_id=None,
        template_name="Deterministic Remit",
        document_kind=PdfDocumentKind.EOB,
        signature_version="sig-2",
        signature_rules=[{"type": "contains_phrase", "phrase": "remittance summary"}],
        anchor_hints={},
        required_fields=[],
        confidence_thresholds={"overall": 0.2},
        active=True,
    )
    snapshot = PdfSignatureSnapshot(
        full_text="Remittance Summary for payer XYZ",
        page_headings=["Remittance Summary"],
        table_headers=[],
        document_kind=DocumentTypeGuess.EOB,
        payer_id=None,
    )
    decision = classifier.classify(snapshot, [template])
    assert decision is not None

    line = PdfLineItem(
        service_date=_field("01/01/2026"),
        code=_field("T1000"),
        billed_amount=_money("50.00"),
        allowed_amount=_money("50.00"),
        paid_amount=_money("50.00"),
        adjustment_codes=[],
    )
    totals = PdfTotals(
        billed_total=_money("50.00"),
        allowed_total=_money("50.00"),
        paid_total=_money("50.00"),
    )
    extract = _sample_extract(line_items=[line], totals=totals)
    updated_extract = attach_template_metadata(
        extract,
        decision.template_id,
        decision.template_confidence,
        decision.signature_version,
    )

    validator = PdfExtractValidator()
    result = validator.validate(updated_extract, template)

    assert result.status == "PASS"
    assert updated_extract.source.signature_version == "sig-2"
    assert result.normalized_payload is not None
    assert result.normalized_payload["source"]["signature_version"] == "sig-2"


def test_cross_check_mismatch_triggers_failure() -> None:
    line = PdfLineItem(
        service_date=_field("01/01/2026"),
        code=_field("99213"),
        billed_amount=_money("30.00"),
        allowed_amount=_money("30.00"),
        paid_amount=_money("30.00"),
        adjustment_codes=[],
    )
    totals = PdfTotals(
        billed_total=_money("100.00"),
        allowed_total=_money("100.00"),
        paid_total=_money("100.00"),
    )
    extract = _sample_extract(line_items=[line], totals=totals)
    validator = PdfExtractValidator()

    result = validator.validate(extract)

    assert result.status == "FAIL"
    assert any("line-item sum mismatch" in reason for reason in result.failure_reasons)
