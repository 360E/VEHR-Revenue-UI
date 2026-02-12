from __future__ import annotations

import logging
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel, Field

from app.core.deps import get_current_membership
from app.db.models.organization_membership import OrganizationMembership
from app.services.tanner_ai.service import (
    TannerAIService,
    TannerAIServiceError,
    get_tanner_ai_service,
)


MAX_AUDIO_UPLOAD_BYTES = 20 * 1024 * 1024
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tanner-ai", tags=["Tanner AI"])


class TannerAIHealthResponse(BaseModel):
    service: str
    status: str


class GenerateRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=20000)
    temperature: float = Field(default=0.2, ge=0.0, le=2.0)


class GenerateResponse(BaseModel):
    text: str


class StructuredNoteRequest(BaseModel):
    transcript: str = Field(min_length=1, max_length=60000)
    note_type: str = Field(min_length=3, max_length=20)


class AssistantRequest(BaseModel):
    message: str = Field(min_length=1, max_length=12000)
    context: str | None = Field(default=None, max_length=20000)


class AssistantResponse(BaseModel):
    reply: str


class TranscriptionResponse(BaseModel):
    transcript: str


def get_tanner_service_dependency() -> TannerAIService:
    return get_tanner_ai_service()


def _raise_service_error(
    *,
    route: str,
    membership: OrganizationMembership,
    exc: TannerAIServiceError,
) -> None:
    logger.warning(
        "tanner_ai_request_failed route=%s org_id=%s user_id=%s status_code=%s detail=%s",
        route,
        membership.organization_id,
        membership.user_id,
        exc.status_code,
        exc.detail,
    )
    raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


@router.get("/health", response_model=TannerAIHealthResponse)
def tanner_ai_health() -> TannerAIHealthResponse:
    return TannerAIHealthResponse(service="Tanner AI", status="ready")


@router.post("/transcribe", response_model=TranscriptionResponse)
async def tanner_ai_transcribe(
    file: UploadFile = File(...),
    membership: OrganizationMembership = Depends(get_current_membership),
    service: TannerAIService = Depends(get_tanner_service_dependency),
) -> TranscriptionResponse:
    temp_path: str | None = None
    try:
        raw = await file.read(MAX_AUDIO_UPLOAD_BYTES + 1)
        if len(raw) > MAX_AUDIO_UPLOAD_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail=f"file_too_large_max_{MAX_AUDIO_UPLOAD_BYTES}_bytes",
            )

        suffix = Path(file.filename or "").suffix or ".bin"
        with NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(raw)
            temp_path = temp_file.name

        transcript = service.transcribe_audio(temp_path)
        return TranscriptionResponse(transcript=transcript)
    except TannerAIServiceError as exc:
        _raise_service_error(route="transcribe", membership=membership, exc=exc)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="tanner_ai_unavailable",
        ) from exc
    finally:
        await file.close()
        if temp_path and os.path.exists(temp_path):
            os.remove(temp_path)


@router.post("/generate", response_model=GenerateResponse)
def tanner_ai_generate(
    payload: GenerateRequest,
    membership: OrganizationMembership = Depends(get_current_membership),
    service: TannerAIService = Depends(get_tanner_service_dependency),
) -> GenerateResponse:
    try:
        text = service.generate_text(payload.prompt, temperature=payload.temperature)
    except TannerAIServiceError as exc:
        _raise_service_error(route="generate", membership=membership, exc=exc)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="tanner_ai_unavailable",
        ) from exc
    return GenerateResponse(text=text)


@router.post("/note")
def tanner_ai_note(
    payload: StructuredNoteRequest,
    membership: OrganizationMembership = Depends(get_current_membership),
    service: TannerAIService = Depends(get_tanner_service_dependency),
) -> dict[str, str]:
    try:
        return service.generate_structured_note(payload.transcript, payload.note_type)
    except TannerAIServiceError as exc:
        _raise_service_error(route="note", membership=membership, exc=exc)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="tanner_ai_unavailable",
        ) from exc


@router.post("/assistant", response_model=AssistantResponse)
def tanner_ai_assistant(
    payload: AssistantRequest,
    membership: OrganizationMembership = Depends(get_current_membership),
    service: TannerAIService = Depends(get_tanner_service_dependency),
) -> AssistantResponse:
    try:
        reply = service.assistant_reply(payload.message, payload.context)
    except TannerAIServiceError as exc:
        _raise_service_error(route="assistant", membership=membership, exc=exc)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="tanner_ai_unavailable",
        ) from exc
    return AssistantResponse(reply=reply)
