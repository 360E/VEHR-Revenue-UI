from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.core.time import utc_now


OPENAI_CHAT_API_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_OPENAI_CHAT_MODEL = "gpt-4o-mini"
DEFAULT_OPENAI_TIMEOUT_SECONDS = 90


class EnterpriseAssistantError(RuntimeError):
    def __init__(self, detail: str, status_code: int = 400) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


@dataclass(frozen=True)
class OpenAiRuntimeConfig:
    api_key: str
    chat_model: str
    timeout_seconds: int


def load_openai_runtime_config_from_env() -> OpenAiRuntimeConfig | None:
    import os

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return None

    chat_model = os.getenv("OPENAI_CHAT_MODEL", "").strip() or DEFAULT_OPENAI_CHAT_MODEL
    timeout_raw = os.getenv("OPENAI_TIMEOUT_SECONDS", "").strip() or str(DEFAULT_OPENAI_TIMEOUT_SECONDS)
    try:
        timeout_seconds = int(timeout_raw)
    except ValueError:
        timeout_seconds = DEFAULT_OPENAI_TIMEOUT_SECONDS
    timeout_seconds = max(5, timeout_seconds)

    return OpenAiRuntimeConfig(api_key=api_key, chat_model=chat_model, timeout_seconds=timeout_seconds)


def _post_openai_chat(*, config: OpenAiRuntimeConfig, messages: list[dict[str, str]]) -> str:
    payload = {
        "model": config.chat_model,
        "temperature": 0.2,
        "messages": messages,
    }
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(timeout=config.timeout_seconds) as client:
            response = client.post(OPENAI_CHAT_API_URL, headers=headers, json=payload)
    except Exception as exc:
        raise EnterpriseAssistantError(f"Unable to reach AI service: {exc}", status_code=503) from exc

    if response.status_code >= 400:
        raise EnterpriseAssistantError("AI service request failed", status_code=503)

    try:
        body = response.json()
    except Exception as exc:
        raise EnterpriseAssistantError("AI service returned invalid response", status_code=503) from exc

    content = body.get("choices", [{}])[0].get("message", {}).get("content", "")
    result = str(content).strip()
    if not result:
        raise EnterpriseAssistantError("AI service returned empty response", status_code=503)
    return result


def build_system_prompt(*, role: str, actions_allowed: set[str] | None = None) -> str:
    allowed = actions_allowed or set()
    # Phase-1: default to draft-only unless explicitly enabled otherwise.
    draft_only = "draft_only" in allowed or not allowed
    guardrails = [
        "You are the VEHR Enterprise Workstation Assistant.",
        "You must be healthcare-safe and enterprise-safe.",
        "Never fabricate patient data or claim access you do not have.",
        "Do not persist PHI into memory unless explicitly instructed and policy allows it.",
        "If a user requests patient-specific action, require explicit patient context (patient_id).",
        "Reject org-wide patient search, unrestricted exports, signing/finalizing charts, and cross-patient reads.",
        "Be concise and actionable.",
    ]
    if draft_only:
        guardrails.append("All outputs are DRAFTS only. Do not claim an action was executed.")
    guardrails.append(f"User role: {role}")
    return "\n".join(guardrails)


def _memory_context_text(memory_items: list[dict[str, Any]]) -> str:
    if not memory_items:
        return "No stored preferences."
    safe_items = []
    for item in memory_items[:30]:
        key = str(item.get("key", "")).strip()
        value = str(item.get("value", "")).strip()
        if not key or not value:
            continue
        safe_items.append({"key": key[:120], "value": value[:800]})
    return json.dumps(safe_items, default=str)


_TIME_RE = re.compile(r"\b(?P<hour>\\d{1,2})(:(?P<minute>\\d{2}))?\\s*(?P<ampm>am|pm)\\b", re.IGNORECASE)


def _parse_time_of_day(message: str) -> tuple[int, int] | None:
    match = _TIME_RE.search(message or "")
    if not match:
        return None
    hour = int(match.group("hour"))
    minute = int(match.group("minute") or "0")
    ampm = (match.group("ampm") or "").lower()
    if hour < 1 or hour > 12 or minute < 0 or minute > 59:
        return None
    if ampm == "pm" and hour != 12:
        hour += 12
    if ampm == "am" and hour == 12:
        hour = 0
    return hour, minute


def extract_reminder_due_at(message: str, *, now: datetime) -> datetime | None:
    lowered = (message or "").lower()
    if "tomorrow" in lowered:
        base_date = (now + timedelta(days=1)).date()
    elif "next week" in lowered:
        base_date = (now + timedelta(days=7)).date()
    else:
        in_match = re.search(r"\\bin\\s+(\\d{1,4})\\s*(minute|minutes|hour|hours|day|days)\\b", lowered)
        if in_match:
            amount = int(in_match.group(1))
            unit = in_match.group(2)
            if unit.startswith("minute"):
                return now + timedelta(minutes=amount)
            if unit.startswith("hour"):
                return now + timedelta(hours=amount)
            if unit.startswith("day"):
                return now + timedelta(days=amount)
        return None

    time_parts = _parse_time_of_day(message)
    hour, minute = time_parts if time_parts else (9, 0)
    due = datetime(base_date.year, base_date.month, base_date.day, hour, minute, tzinfo=timezone.utc)
    return due


def wants_reminder(message: str) -> bool:
    lowered = (message or "").strip().lower()
    return "remind me" in lowered or lowered.startswith("reminder") or "set a reminder" in lowered


def build_reminder_summary(*, title: str, due_at: datetime, channels: list[str], repeat_mode: str) -> str:
    when = due_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    channels_text = ", ".join(channels) if channels else "in_chat"
    repeat_text = repeat_mode or "one_shot"
    return (
        "Reminder draft created:\n"
        f"- What: {title}\n"
        f"- When (UTC): {when}\n"
        f"- Channels: {channels_text}\n"
        f"- Repeats: {repeat_text}"
    )


def generate_reply(
    *,
    role: str,
    message: str,
    context: dict[str, Any],
    history: list[dict[str, str]],
    memory_items: list[dict[str, Any]],
    actions_allowed: set[str] | None = None,
) -> tuple[str, dict[str, Any]]:
    config = load_openai_runtime_config_from_env()
    if config is None:
        fallback = (
            "Enterprise Assistant is not fully configured (missing OPENAI_API_KEY). "
            "I can still help with drafting templates, checklists, and safe next steps. "
            "If you need reminder scheduling, use the Reminders panel."
        )
        return fallback, {"fallback": True, "warnings": ["OPENAI_API_KEY not configured"]}

    messages: list[dict[str, str]] = [
        {"role": "system", "content": build_system_prompt(role=role, actions_allowed=actions_allowed)},
        {"role": "system", "content": f"Context: {json.dumps(context, default=str)}"},
        {"role": "system", "content": f"User memory: {_memory_context_text(memory_items)}"},
    ]
    for item in history[-20:]:
        item_role = (item.get("role") or "").strip().lower()
        if item_role not in {"user", "assistant"}:
            continue
        content = (item.get("content") or "").strip()
        if not content:
            continue
        messages.append({"role": item_role, "content": content})
    messages.append({"role": "user", "content": message.strip()})

    try:
        reply = _post_openai_chat(config=config, messages=messages)
        return reply, {"fallback": False, "warnings": []}
    except EnterpriseAssistantError:
        degraded = (
            "I couldn't reach the AI service right now. "
            "I can still help you structure the task. Tell me:\n"
            "1) the goal\n"
            "2) any constraints (role/policy)\n"
            "3) whether a patient is in scope (patient_id required)\n"
        )
        return degraded, {"fallback": True, "warnings": ["ai_service_unavailable"]}
