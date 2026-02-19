from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.db.models.claim import ClaimStatus
from app.db.models.claim_event import ClaimEventType


class ClaimNormalizer:
    REQUIRED_ROOT_KEYS = {"claim", "lines", "events"}
    REQUIRED_CLAIM_KEYS = {"org_id"}
    REQUIRED_LINE_KEYS = {"billed_amount"}
    REQUIRED_EVENT_KEYS = {"event_type"}

    def normalize(self, raw_json: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(raw_json, dict):
            raise ValueError("raw_json must be a dict")
        missing_root = self.REQUIRED_ROOT_KEYS - set(raw_json.keys())
        if missing_root:
            raise ValueError(f"Missing required keys: {', '.join(sorted(missing_root))}")

        claim_payload = deepcopy(raw_json.get("claim"))
        lines_payload = deepcopy(raw_json.get("lines"))
        events_payload = deepcopy(raw_json.get("events"))

        if not isinstance(claim_payload, dict):
            raise ValueError("claim must be a dict")
        if not isinstance(lines_payload, list):
            raise ValueError("lines must be a list")
        if not isinstance(events_payload, list):
            raise ValueError("events must be a list")

        missing_claim = self.REQUIRED_CLAIM_KEYS - set(claim_payload.keys())
        if missing_claim:
            raise ValueError(f"claim missing required keys: {', '.join(sorted(missing_claim))}")

        if "status" in claim_payload and claim_payload["status"] is not None:
            try:
                ClaimStatus(claim_payload["status"])
            except ValueError as exc:
                raise ValueError("claim.status must be a valid ClaimStatus") from exc

        normalized_lines: list[dict[str, Any]] = []
        for line in lines_payload:
            if not isinstance(line, dict):
                raise ValueError("each line must be a dict")
            missing_line = self.REQUIRED_LINE_KEYS - set(line.keys())
            if missing_line:
                raise ValueError(f"line missing required keys: {', '.join(sorted(missing_line))}")
            normalized_lines.append(deepcopy(line))

        normalized_events: list[dict[str, Any]] = []
        for event in events_payload:
            if not isinstance(event, dict):
                raise ValueError("each event must be a dict")
            missing_event = self.REQUIRED_EVENT_KEYS - set(event.keys())
            if missing_event:
                raise ValueError(f"event missing required keys: {', '.join(sorted(missing_event))}")
            try:
                ClaimEventType(event["event_type"])
            except ValueError as exc:
                raise ValueError("event.event_type must be a valid ClaimEventType") from exc
            normalized_events.append(deepcopy(event))

        return {
            "claim": deepcopy(claim_payload),
            "lines": normalized_lines,
            "events": normalized_events,
        }
