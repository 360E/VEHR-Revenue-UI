from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.rbac import has_permission_for_organization
from app.db.models.form_template import FormTemplate
from app.db.models.service import Service
from app.db.models.service_document_template import ServiceDocumentTemplate
from app.services.integration_tokens import TokenEncryptionError, decrypt_token, encrypt_token
from app.services.storage import generate_presigned_get_url

OPENAI_CHAT_API_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_TRANSCRIBE_API_URL = "https://api.openai.com/v1/audio/transcriptions"
DEFAULT_OPENAI_CHAT_MODEL = "gpt-4o-mini"
DEFAULT_OPENAI_TRANSCRIBE_MODEL = "whisper-1"
DEFAULT_OPENAI_TIMEOUT_SECONDS = 90
DEFAULT_SCRIBE_AUDIO_RETENTION_DAYS = 14


class AiCopilotError(RuntimeError):
    def __init__(self, detail: str, status_code: int = 400) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


@dataclass(frozen=True)
class OpenAiRuntimeConfig:
    api_key: str
    chat_model: str
    transcribe_model: str
    timeout_seconds: int


def load_openai_runtime_config() -> OpenAiRuntimeConfig:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise AiCopilotError("OPENAI_API_KEY is not configured", status_code=503)

    chat_model = os.getenv("OPENAI_CHAT_MODEL", "").strip() or DEFAULT_OPENAI_CHAT_MODEL
    transcribe_model = os.getenv("OPENAI_TRANSCRIBE_MODEL", "").strip() or DEFAULT_OPENAI_TRANSCRIBE_MODEL
    timeout_raw = os.getenv("OPENAI_TIMEOUT_SECONDS", "").strip() or str(DEFAULT_OPENAI_TIMEOUT_SECONDS)
    try:
        timeout_seconds = int(timeout_raw)
    except ValueError as exc:
        raise AiCopilotError("OPENAI_TIMEOUT_SECONDS must be an integer", status_code=500) from exc
    if timeout_seconds <= 0:
        raise AiCopilotError("OPENAI_TIMEOUT_SECONDS must be greater than 0", status_code=500)

    return OpenAiRuntimeConfig(
        api_key=api_key,
        chat_model=chat_model,
        transcribe_model=transcribe_model,
        timeout_seconds=timeout_seconds,
    )


def encrypt_sensitive_text(value: str) -> str:
    if not value:
        return ""
    try:
        return encrypt_token(value, key_env="INTEGRATION_TOKEN_KEY")
    except TokenEncryptionError as exc:
        raise AiCopilotError(f"Unable to encrypt sensitive payload: {exc}", status_code=500) from exc


def decrypt_sensitive_text(value: str) -> str:
    if not value:
        return ""
    try:
        return decrypt_token(value, key_env="INTEGRATION_TOKEN_KEY")
    except TokenEncryptionError as exc:
        raise AiCopilotError(f"Unable to decrypt sensitive payload: {exc}", status_code=500) from exc


def build_system_prompt() -> str:
    return (
        "You are VEHR Copilot.\n"
        "You support staff workflows.\n"
        "Never access data outside the current organization.\n"
        "Never fabricate patient data.\n"
        "Only use PHI explicitly provided by user.\n"
        "If uncertain, ask a clarifying question.\n"
        "Be concise and actionable."
    )


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
        raise AiCopilotError(f"Unable to reach AI service: {exc}", status_code=503) from exc

    if response.status_code >= 400:
        raise AiCopilotError("AI service request failed", status_code=503)

    try:
        body = response.json()
    except Exception as exc:
        raise AiCopilotError("AI service returned invalid response", status_code=503) from exc

    content = (
        body.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )
    result = str(content).strip()
    if not result:
        raise AiCopilotError("AI service returned empty response", status_code=503)
    return result


def search_policies(
    *,
    db: Session,
    organization_id: str,
    role: str,
    query: str,
) -> list[dict[str, str]]:
    if not has_permission_for_organization(
        db,
        organization_id=organization_id,
        role=role,
        permission="forms:read",
    ):
        raise AiCopilotError("Insufficient permissions for policy search", status_code=403)

    normalized = query.strip().lower()
    if not normalized:
        return []
    pattern = f"%{normalized}%"

    templates = db.execute(
        select(FormTemplate).where(
            FormTemplate.organization_id == organization_id,
            (func.lower(FormTemplate.name).like(pattern) | func.lower(func.coalesce(FormTemplate.description, "")).like(pattern)),
        )
        .order_by(FormTemplate.created_at.desc())
        .limit(10)
    ).scalars().all()

    service_templates = db.execute(
        select(ServiceDocumentTemplate, Service, FormTemplate)
        .join(Service, Service.id == ServiceDocumentTemplate.service_id)
        .join(FormTemplate, FormTemplate.id == ServiceDocumentTemplate.template_id)
        .where(
            ServiceDocumentTemplate.organization_id == organization_id,
            (
                func.lower(Service.name).like(pattern)
                | func.lower(FormTemplate.name).like(pattern)
                | func.lower(ServiceDocumentTemplate.requirement_type).like(pattern)
            ),
        )
        .order_by(ServiceDocumentTemplate.created_at.desc())
        .limit(10)
    ).all()

    results: list[dict[str, str]] = []
    for row in templates:
        snippet = (row.description or row.name or "").strip()
        results.append(
            {
                "id": row.id,
                "title": row.name,
                "snippet": snippet[:220],
            }
        )
    for mapping_row, service_row, template_row in service_templates:
        results.append(
            {
                "id": mapping_row.id,
                "title": f"{service_row.name} - {template_row.name}",
                "snippet": f"{mapping_row.requirement_type} ({mapping_row.trigger})",
            }
        )
    return results[:10]


def draft_template(*, template_type: str, inputs: dict[str, Any]) -> str:
    normalized = template_type.strip().upper()
    subject = str(inputs.get("subject", "")).strip() or "Subject"
    patient = str(inputs.get("patient_name", "")).strip() or "[Patient Name]"
    if normalized == "SOAP":
        return (
            "S: [Subjective summary]\n"
            "O: [Objective findings]\n"
            "A: [Assessment]\n"
            "P: [Plan and next steps]\n"
        )
    if normalized == "DAP":
        return (
            "D: [Data gathered during encounter]\n"
            "A: [Clinical assessment]\n"
            "P: [Plan, interventions, follow-up]\n"
        )
    return (
        f"Re: {subject}\n\n"
        f"Dear {patient},\n\n"
        "[Insert concise letter body]\n\n"
        "Sincerely,\n"
        "[Provider Name]\n"
    )


def load_scribe_audio_retention_days() -> int:
    raw = os.getenv("ScribeAudioRetentionDays", "").strip() or str(DEFAULT_SCRIBE_AUDIO_RETENTION_DAYS)
    try:
        days = int(raw)
    except ValueError as exc:
        raise AiCopilotError("ScribeAudioRetentionDays must be an integer", status_code=500) from exc
    if days <= 0:
        raise AiCopilotError("ScribeAudioRetentionDays must be greater than 0", status_code=500)
    return days


def mark_capture_for_deletion(
    *,
    created_at: datetime | None,
    retention_days: int | None = None,
) -> datetime:
    days = retention_days if retention_days is not None else load_scribe_audio_retention_days()
    anchor = created_at or datetime.now(timezone.utc)
    if anchor.tzinfo is None:
        anchor = anchor.replace(tzinfo=timezone.utc)
    return anchor + timedelta(days=days)


def _tool_context_text(tool_results: dict[str, Any]) -> str:
    if not tool_results:
        return ""
    try:
        return json.dumps(tool_results, default=str)
    except Exception:
        return str(tool_results)


def generate_copilot_response(
    *,
    db: Session,
    organization_id: str,
    role: str,
    message: str,
    context: dict[str, Any],
    history: list[dict[str, str]],
) -> tuple[str, dict[str, Any]]:
    tool_results: dict[str, Any] = {}
    lowered = message.strip().lower()
    quick_action = str(context.get("quick_action", "")).strip().lower()

    if "policy" in lowered or quick_action == "find_policy":
        policy_results = search_policies(
            db=db,
            organization_id=organization_id,
            role=role,
            query=message,
        )
        tool_results["search_policies"] = policy_results

    if quick_action in {"draft_note", "draft_letter"} or any(token in lowered for token in ["draft soap", "draft dap", "draft letter"]):
        template_type = "LETTER"
        if "soap" in lowered:
            template_type = "SOAP"
        elif "dap" in lowered:
            template_type = "DAP"
        elif quick_action == "draft_note":
            template_type = "SOAP"
        draft_result = draft_template(
            template_type=template_type,
            inputs={"subject": message},
        )
        tool_results["draft_template"] = {
            "template_type": template_type,
            "content": draft_result,
        }

    messages: list[dict[str, str]] = [
        {"role": "system", "content": build_system_prompt()},
        {"role": "system", "content": f"Context: {json.dumps(context, default=str)}"},
    ]
    if tool_results:
        messages.append(
            {
                "role": "system",
                "content": f"Tool outputs: {_tool_context_text(tool_results)}",
            }
        )
    for item in history[-20:]:
        role = item.get("role", "").strip().lower()
        if role not in {"user", "assistant"}:
            continue
        content = str(item.get("content", "")).strip()
        if not content:
            continue
        messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": message.strip()})

    try:
        config = load_openai_runtime_config()
        response = _post_openai_chat(config=config, messages=messages)
    except AiCopilotError:
        if "draft_template" in tool_results:
            fallback_content = str(tool_results["draft_template"].get("content", "")).strip()
            if fallback_content:
                return fallback_content, {"tool_results": tool_results, "fallback": True}
        if "search_policies" in tool_results:
            rows = tool_results["search_policies"]
            if rows:
                preview = "\n".join(
                    f"- {item.get('title', 'Policy')}: {item.get('snippet', '')}"
                    for item in rows[:5]
                )
                return f"I found these policy references:\n{preview}", {"tool_results": tool_results, "fallback": True}
        raise

    return response, {"tool_results": tool_results}


def transcribe_capture_audio(*, encrypted_s3_key: str) -> str:
    config = load_openai_runtime_config()
    s3_key = decrypt_sensitive_text(encrypted_s3_key)
    if not s3_key:
        raise AiCopilotError("Capture storage key is missing", status_code=500)

    presigned_url = generate_presigned_get_url(s3_key, expires=600)
    try:
        with httpx.Client(timeout=config.timeout_seconds) as client:
            source_response = client.get(presigned_url)
    except Exception as exc:
        raise AiCopilotError(f"Unable to retrieve capture audio: {exc}", status_code=502) from exc
    if source_response.status_code >= 400:
        raise AiCopilotError("Unable to retrieve capture audio", status_code=502)

    files = {
        "file": ("capture.webm", source_response.content, "application/octet-stream"),
    }
    data = {"model": config.transcribe_model}
    headers = {"Authorization": f"Bearer {config.api_key}"}

    try:
        with httpx.Client(timeout=config.timeout_seconds) as client:
            response = client.post(OPENAI_TRANSCRIBE_API_URL, headers=headers, data=data, files=files)
    except Exception as exc:
        raise AiCopilotError(f"Unable to reach transcription service: {exc}", status_code=503) from exc

    if response.status_code >= 400:
        raise AiCopilotError("Transcription service request failed", status_code=503)
    try:
        payload = response.json()
    except Exception as exc:
        raise AiCopilotError("Transcription service returned invalid response", status_code=503) from exc

    transcript = str(payload.get("text", "")).strip()
    if not transcript:
        raise AiCopilotError("Transcription service returned empty transcript", status_code=503)
    return transcript


def generate_scribe_note(*, transcript_text: str, note_type: str) -> str:
    normalized = note_type.strip().upper()
    if normalized not in {"SOAP", "DAP"}:
        raise AiCopilotError("note_type must be SOAP or DAP", status_code=400)
    if not transcript_text.strip():
        raise AiCopilotError("Transcript text is required", status_code=400)

    system_prompt = (
        "You are a clinical documentation assistant.\n"
        "Generate a concise draft note in the requested format.\n"
        "Do not fabricate facts. If information is missing, state that explicitly.\n"
        "Use professional clinical language."
    )
    user_prompt = (
        f"Format: {normalized}\n"
        f"Transcript:\n{transcript_text}"
    )

    try:
        config = load_openai_runtime_config()
        content = _post_openai_chat(
            config=config,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        )
    except AiCopilotError:
        shell = draft_template(template_type=normalized, inputs={})
        return (
            f"[AI Draft - Requires provider review before chart insertion]\n\n"
            f"{shell}\n"
            "Transcript summary:\n"
            f"{transcript_text[:1500]}"
        )

    return f"[AI Draft - Requires provider review before chart insertion]\n\n{content}"
