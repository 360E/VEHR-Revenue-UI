from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable, Sequence

from app.db.models.pdf_template_registry import PdfDocumentKind, PdfTemplateRegistry
from app.services.pdf_extract_contract import DocumentTypeGuess, compute_raw_text_hashes


@dataclass(frozen=True)
class PdfSignatureSnapshot:
    full_text: str
    page_headings: list[str]
    table_headers: list[str]
    document_kind: DocumentTypeGuess
    payer_id: str | None = None

    def normalized_text(self) -> str:
        return (self.full_text or "").lower()


@dataclass(frozen=True)
class TemplateMatchResult:
    template_id: str
    template_name: str
    signature_version: str
    template_confidence: float
    applied_rules: list[str]
    document_kind: PdfDocumentKind


class PdfTemplateClassifier:
    def __init__(self, default_threshold: float = 0.75) -> None:
        self._default_threshold = default_threshold

    def classify(
        self,
        snapshot: PdfSignatureSnapshot,
        templates: Sequence[PdfTemplateRegistry],
    ) -> TemplateMatchResult | None:
        candidates: list[TemplateMatchResult] = []
        scored: list[tuple[float, int, TemplateMatchResult]] = []

        for template in templates:
            if not template.active:
                continue
            if not self._document_kind_matches(snapshot.document_kind, template.document_kind):
                continue
            if template.payer_id and snapshot.payer_id and template.payer_id != snapshot.payer_id:
                continue

            rules = self._normalize_rules(template.signature_rules)
            matched_count, matched_rule_types = self._score_rules(snapshot, rules)
            total_rules = len(rules)
            normalized_score = matched_count / total_rules if total_rules else 0.0
            threshold = float((template.confidence_thresholds or {}).get("overall", self._default_threshold))

            if normalized_score >= threshold:
                result = TemplateMatchResult(
                    template_id=template.id,
                    template_name=template.template_name,
                    signature_version=template.signature_version,
                    template_confidence=normalized_score,
                    applied_rules=matched_rule_types,
                    document_kind=template.document_kind,
                )
                scored.append((normalized_score, matched_count, result))
                candidates.append(result)

        if not scored:
            return None

        scored.sort(key=lambda item: (item[0], item[1]), reverse=True)
        top = scored[0]
        if len(scored) > 1 and scored[0][0] == scored[1][0] and scored[0][1] == scored[1][1]:
            return None
        return top[2]

    def _document_kind_matches(self, extracted: DocumentTypeGuess, template_kind: PdfDocumentKind) -> bool:
        if template_kind == PdfDocumentKind.UNKNOWN:
            return True
        return extracted.value == template_kind.value

    def _normalize_rules(self, signature_rules: dict | list | None) -> list[dict]:
        if not signature_rules:
            return []
        if isinstance(signature_rules, list):
            return [r for r in signature_rules if isinstance(r, dict)]
        if isinstance(signature_rules, dict):
            rules = signature_rules.get("rules")
            if isinstance(rules, list):
                return [r for r in rules if isinstance(r, dict)]
        return []

    def _score_rules(self, snapshot: PdfSignatureSnapshot, rules: Iterable[dict]) -> tuple[int, list[str]]:
        matched = 0
        matched_rule_types: list[str] = []
        normalized_text = snapshot.normalized_text()

        for rule in rules:
            rule_type = rule.get("type")
            if not rule_type:
                continue

            if rule_type == "contains_phrase":
                phrase = (rule.get("phrase") or "").lower()
                if phrase and phrase in normalized_text:
                    matched += 1
                    matched_rule_types.append(rule_type)
            elif rule_type == "regex_match":
                pattern = rule.get("pattern")
                if pattern and re.search(pattern, normalized_text, flags=re.IGNORECASE):
                    matched += 1
                    matched_rule_types.append(rule_type)
            elif rule_type == "table_header_match":
                header = (rule.get("header") or "").lower()
                if header and self._list_contains(snapshot.table_headers, header):
                    matched += 1
                    matched_rule_types.append(rule_type)
            elif rule_type == "nearby_terms":
                terms = [t.lower() for t in rule.get("terms", []) if isinstance(t, str)]
                window = int(rule.get("window", 80))
                if terms and self._terms_within_window(normalized_text, terms, window):
                    matched += 1
                    matched_rule_types.append(rule_type)
            elif rule_type == "page_heading_match":
                heading = (rule.get("heading") or "").lower()
                if heading and self._list_contains(snapshot.page_headings, heading):
                    matched += 1
                    matched_rule_types.append(rule_type)

        return matched, matched_rule_types

    def _list_contains(self, haystack: Iterable[str], needle: str) -> bool:
        lowered = [item.lower() for item in haystack if item]
        return any(needle in item for item in lowered)

    def _terms_within_window(self, text: str, terms: list[str], window: int) -> bool:
        positions: list[int] = []
        for term in terms:
            idx = text.find(term)
            if idx == -1:
                return False
            positions.append(idx)
        if not positions:
            return False
        return max(positions) - min(positions) <= window


def build_signature_snapshot_from_pages(
    pages: Sequence[str],
    document_kind: DocumentTypeGuess,
    payer_id: str | None = None,
    table_headers: Sequence[str] | None = None,
) -> PdfSignatureSnapshot:
    full_text = "\n".join([p or "" for p in pages])
    headings = [p.splitlines()[0] for p in pages if p and p.splitlines()]
    headers = list(table_headers or [])
    return PdfSignatureSnapshot(
        full_text=full_text,
        page_headings=headings,
        table_headers=headers,
        document_kind=document_kind,
        payer_id=payer_id,
    )


def compute_page_hashes(pages: Sequence[str]) -> list[str]:
    return compute_raw_text_hashes(pages)
