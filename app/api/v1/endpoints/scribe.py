from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_membership, require_permission
from app.core.time import utc_now
from app.db.models.encounter import Encounter
from app.db.models.patient_note import PatientNote
from app.db.models.patient_service_enrollment import PatientServiceEnrollment
from app.db.models.scribe_capture import ScribeCapture
from app.db.models.scribe_note_draft import ScribeNoteDraft
from app.db.models.scribe_transcript import ScribeTranscript
from app.db.models.service import Service
from app.db.session import get_db
from app.services.ai_copilot import (
    AiCopilotError,
    decrypt_sensitive_text,
    encrypt_sensitive_text,
    generate_scribe_note,
    mark_capture_for_deletion,
    transcribe_capture_audio,
)
from app.services.audit import log_event
from app.services.storage import build_object_key, generate_presigned_put_url, get_s3_settings


router = APIRouter(tags=["AI Scribe"])

SCRIBE_PERMISSION = "patients:write"
_NOTE_VISIBILITIES = {"clinical_only", "legal_and_clinical"}


class ScribeCaptureCreateRequest(BaseModel):
    encounter_id: str
    filename: str = Field(default="capture.webm", min_length=1, max_length=255)
    content_type: str = Field(default="audio/webm", min_length=1, max_length=120)


class ScribeCaptureCreateResponse(BaseModel):
    id: str
    encounter_id: str
    upload_url: str
    upload_method: str
    upload_headers: dict[str, str]
    marked_for_deletion_at: datetime


class ScribeCaptureCompleteRequest(BaseModel):
    duration_sec: int | None = Field(default=None, ge=0, le=60 * 60 * 8)


class ScribeCaptureRead(BaseModel):
    id: str
    encounter_id: str
    duration_sec: int | None = None
    created_at: datetime
    marked_for_deletion_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ScribeTranscriptRead(BaseModel):
    id: str
    capture_id: str
    text: str
    created_at: datetime


class ScribeDraftGenerateRequest(BaseModel):
    note_type: str = Field(pattern="^(SOAP|DAP)$")


class ScribeDraftUpdateRequest(BaseModel):
    content: str = Field(min_length=1, max_length=50000)


class ScribeDraftRead(BaseModel):
    id: str
    capture_id: str
    note_type: str
    content: str
    created_at: datetime
    updated_at: datetime


class ScribeInsertIntoChartRequest(BaseModel):
    primary_service_id: str | None = None
    visibility: str = "clinical_only"


class ScribeInsertIntoChartResponse(BaseModel):
    note_id: str
    patient_id: str
    encounter_id: str
    status: str


def _normalize_content_type(content_type: str) -> str:
    normalized = content_type.strip().lower()
    if not normalized:
        return "application/octet-stream"
    if any(ch in normalized for ch in ("\n", "\r", ";")):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid content_type")
    if "/" not in normalized:
        return "application/octet-stream"
    return normalized


def _normalize_note_type(value: str) -> str:
    normalized = value.strip().upper()
    if normalized not in {"SOAP", "DAP"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="note_type must be SOAP or DAP")
    return normalized


def _normalize_visibility(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in _NOTE_VISIBILITIES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid note visibility")
    return normalized


def _get_encounter_or_404(*, db: Session, encounter_id: str, organization_id: str) -> Encounter:
    row = db.execute(
        select(Encounter).where(
            Encounter.id == encounter_id,
            Encounter.organization_id == organization_id,
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Encounter not found")
    return row


def _get_capture_or_404(*, db: Session, capture_id: str, organization_id: str, user_id: str) -> ScribeCapture:
    row = db.execute(
        select(ScribeCapture).where(
            ScribeCapture.id == capture_id,
            ScribeCapture.organization_id == organization_id,
            ScribeCapture.user_id == user_id,
        )
    ).scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Capture not found")
    return row


def _get_draft_or_404(*, db: Session, draft_id: str, organization_id: str, user_id: str) -> tuple[ScribeNoteDraft, ScribeCapture]:
    row = db.execute(
        select(ScribeNoteDraft, ScribeCapture)
        .join(ScribeCapture, ScribeCapture.id == ScribeNoteDraft.capture_id)
        .where(
            ScribeNoteDraft.id == draft_id,
            ScribeCapture.organization_id == organization_id,
            ScribeCapture.user_id == user_id,
        )
    ).one_or_none()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Draft not found")
    return row[0], row[1]


def _decrypt_scribe_text(value: str) -> str:
    try:
        return decrypt_sensitive_text(value)
    except AiCopilotError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc


def _resolve_service_id_for_note(
    *,
    db: Session,
    organization_id: str,
    patient_id: str,
    requested_service_id: str | None,
) -> str:
    if requested_service_id:
        service = db.execute(
            select(Service).where(
                Service.id == requested_service_id,
                Service.organization_id == organization_id,
            )
        ).scalar_one_or_none()
        if not service:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
        return service.id

    active_enrollment = db.execute(
        select(PatientServiceEnrollment)
        .where(
            PatientServiceEnrollment.organization_id == organization_id,
            PatientServiceEnrollment.patient_id == patient_id,
            PatientServiceEnrollment.status == "active",
        )
        .order_by(PatientServiceEnrollment.start_date.desc(), PatientServiceEnrollment.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if active_enrollment:
        return active_enrollment.service_id

    latest_enrollment = db.execute(
        select(PatientServiceEnrollment)
        .where(
            PatientServiceEnrollment.organization_id == organization_id,
            PatientServiceEnrollment.patient_id == patient_id,
        )
        .order_by(PatientServiceEnrollment.start_date.desc(), PatientServiceEnrollment.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if latest_enrollment:
        return latest_enrollment.service_id

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="primary_service_id is required when patient has no enrollments",
    )


@router.post("/scribe/captures", response_model=ScribeCaptureCreateResponse, status_code=status.HTTP_201_CREATED)
def create_scribe_capture(
    payload: ScribeCaptureCreateRequest,
    db: Session = Depends(get_db),
    membership=Depends(get_current_membership),
    _: None = Depends(require_permission(SCRIBE_PERMISSION)),
) -> ScribeCaptureCreateResponse:
    _get_encounter_or_404(
        db=db,
        encounter_id=payload.encounter_id,
        organization_id=membership.organization_id,
    )

    content_type = _normalize_content_type(payload.content_type)

    try:
        settings = get_s3_settings()
        storage_key = build_object_key(
            organization_id=membership.organization_id,
            resource="scribe-audio",
            filename=payload.filename,
        )
        upload_url = generate_presigned_put_url(
            key=storage_key,
            content_type=content_type,
            expires=settings.presign_expires_seconds,
            server_side_encryption="AES256",
        )
        encrypted_key = encrypt_sensitive_text(storage_key)
    except AiCopilotError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Failed to create audio upload URL") from exc

    now = utc_now()
    try:
        marked_for_deletion_at = mark_capture_for_deletion(created_at=now)
    except AiCopilotError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    capture = ScribeCapture(
        organization_id=membership.organization_id,
        user_id=membership.user_id,
        encounter_id=payload.encounter_id,
        s3_key=encrypted_key,
        created_at=now,
        deleted_at=marked_for_deletion_at,
    )
    db.add(capture)
    db.commit()
    db.refresh(capture)

    log_event(
        db,
        action="scribe_capture_created",
        entity_type="scribe_capture",
        entity_id=capture.id,
        organization_id=membership.organization_id,
        actor=membership.user.email,
        metadata={
            "capture_id": capture.id,
            "encounter_id": payload.encounter_id,
            "has_duration": False,
        },
    )

    return ScribeCaptureCreateResponse(
        id=capture.id,
        encounter_id=capture.encounter_id,
        upload_url=upload_url,
        upload_method="PUT",
        upload_headers={
            "Content-Type": content_type,
            "x-amz-server-side-encryption": "AES256",
        },
        marked_for_deletion_at=marked_for_deletion_at,
    )


@router.post("/scribe/captures/{capture_id}/complete", response_model=ScribeCaptureRead)
def complete_scribe_capture(
    capture_id: str,
    payload: ScribeCaptureCompleteRequest,
    db: Session = Depends(get_db),
    membership=Depends(get_current_membership),
    _: None = Depends(require_permission(SCRIBE_PERMISSION)),
) -> ScribeCaptureRead:
    capture = _get_capture_or_404(
        db=db,
        capture_id=capture_id,
        organization_id=membership.organization_id,
        user_id=membership.user_id,
    )

    if payload.duration_sec is not None:
        capture.duration_sec = payload.duration_sec
    if capture.deleted_at is None:
        try:
            capture.deleted_at = mark_capture_for_deletion(created_at=capture.created_at)
        except AiCopilotError as exc:
            raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    db.add(capture)
    db.commit()
    db.refresh(capture)

    log_event(
        db,
        action="scribe_capture_completed",
        entity_type="scribe_capture",
        entity_id=capture.id,
        organization_id=membership.organization_id,
        actor=membership.user.email,
        metadata={
            "capture_id": capture.id,
            "has_duration": payload.duration_sec is not None,
        },
    )

    return ScribeCaptureRead(
        id=capture.id,
        encounter_id=capture.encounter_id,
        duration_sec=capture.duration_sec,
        created_at=capture.created_at,
        marked_for_deletion_at=capture.deleted_at,
    )


@router.post("/scribe/captures/{capture_id}/transcribe", response_model=ScribeTranscriptRead)
def transcribe_scribe_capture(
    capture_id: str,
    db: Session = Depends(get_db),
    membership=Depends(get_current_membership),
    _: None = Depends(require_permission(SCRIBE_PERMISSION)),
) -> ScribeTranscriptRead:
    capture = _get_capture_or_404(
        db=db,
        capture_id=capture_id,
        organization_id=membership.organization_id,
        user_id=membership.user_id,
    )

    try:
        transcript_text = transcribe_capture_audio(encrypted_s3_key=capture.s3_key)
        encrypted_transcript = encrypt_sensitive_text(transcript_text)
    except AiCopilotError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    transcript = ScribeTranscript(capture_id=capture.id, text=encrypted_transcript)
    db.add(transcript)
    db.commit()
    db.refresh(transcript)

    log_event(
        db,
        action="scribe_transcribed",
        entity_type="scribe_capture",
        entity_id=capture.id,
        organization_id=membership.organization_id,
        actor=membership.user.email,
        metadata={
            "capture_id": capture.id,
            "transcript_id": transcript.id,
            "transcript_char_count": len(transcript_text),
        },
    )

    return ScribeTranscriptRead(
        id=transcript.id,
        capture_id=transcript.capture_id,
        text=transcript_text,
        created_at=transcript.created_at,
    )


@router.post("/scribe/captures/{capture_id}/draft-note", response_model=ScribeDraftRead)
def generate_scribe_draft_note(
    capture_id: str,
    payload: ScribeDraftGenerateRequest,
    db: Session = Depends(get_db),
    membership=Depends(get_current_membership),
    _: None = Depends(require_permission(SCRIBE_PERMISSION)),
) -> ScribeDraftRead:
    capture = _get_capture_or_404(
        db=db,
        capture_id=capture_id,
        organization_id=membership.organization_id,
        user_id=membership.user_id,
    )

    note_type = _normalize_note_type(payload.note_type)

    transcript = db.execute(
        select(ScribeTranscript)
        .where(ScribeTranscript.capture_id == capture.id)
        .order_by(ScribeTranscript.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if not transcript:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No transcript available for capture")

    transcript_text = _decrypt_scribe_text(transcript.text)

    try:
        generated_content = generate_scribe_note(
            transcript_text=transcript_text,
            note_type=note_type,
        )
        encrypted_content = encrypt_sensitive_text(generated_content)
    except AiCopilotError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    existing = db.execute(
        select(ScribeNoteDraft)
        .where(
            ScribeNoteDraft.capture_id == capture.id,
            ScribeNoteDraft.note_type == note_type,
        )
        .order_by(ScribeNoteDraft.updated_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    if existing:
        existing.content = encrypted_content
        draft = existing
    else:
        draft = ScribeNoteDraft(
            capture_id=capture.id,
            note_type=note_type,
            content=encrypted_content,
        )

    db.add(draft)
    db.commit()
    db.refresh(draft)

    log_event(
        db,
        action="scribe_draft_generated",
        entity_type="scribe_capture",
        entity_id=capture.id,
        organization_id=membership.organization_id,
        actor=membership.user.email,
        metadata={
            "capture_id": capture.id,
            "draft_id": draft.id,
            "note_type": note_type,
        },
    )

    return ScribeDraftRead(
        id=draft.id,
        capture_id=draft.capture_id,
        note_type=draft.note_type,
        content=generated_content,
        created_at=draft.created_at,
        updated_at=draft.updated_at,
    )


@router.put("/scribe/drafts/{draft_id}", response_model=ScribeDraftRead)
def update_scribe_draft(
    draft_id: str,
    payload: ScribeDraftUpdateRequest,
    db: Session = Depends(get_db),
    membership=Depends(get_current_membership),
    _: None = Depends(require_permission(SCRIBE_PERMISSION)),
) -> ScribeDraftRead:
    draft, capture = _get_draft_or_404(
        db=db,
        draft_id=draft_id,
        organization_id=membership.organization_id,
        user_id=membership.user_id,
    )

    content = payload.content.strip()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="content is required")

    try:
        draft.content = encrypt_sensitive_text(content)
    except AiCopilotError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    db.add(draft)
    db.commit()
    db.refresh(draft)

    log_event(
        db,
        action="scribe_draft_updated",
        entity_type="scribe_capture",
        entity_id=capture.id,
        organization_id=membership.organization_id,
        actor=membership.user.email,
        metadata={
            "capture_id": capture.id,
            "draft_id": draft.id,
            "note_type": draft.note_type,
        },
    )

    return ScribeDraftRead(
        id=draft.id,
        capture_id=draft.capture_id,
        note_type=draft.note_type,
        content=content,
        created_at=draft.created_at,
        updated_at=draft.updated_at,
    )


@router.post("/scribe/drafts/{draft_id}/insert-into-chart", response_model=ScribeInsertIntoChartResponse)
def insert_scribe_draft_into_chart(
    draft_id: str,
    payload: ScribeInsertIntoChartRequest,
    db: Session = Depends(get_db),
    membership=Depends(get_current_membership),
    _: None = Depends(require_permission(SCRIBE_PERMISSION)),
) -> ScribeInsertIntoChartResponse:
    draft, capture = _get_draft_or_404(
        db=db,
        draft_id=draft_id,
        organization_id=membership.organization_id,
        user_id=membership.user_id,
    )
    encounter = _get_encounter_or_404(
        db=db,
        encounter_id=capture.encounter_id,
        organization_id=membership.organization_id,
    )

    service_id = _resolve_service_id_for_note(
        db=db,
        organization_id=membership.organization_id,
        patient_id=encounter.patient_id,
        requested_service_id=payload.primary_service_id,
    )
    visibility = _normalize_visibility(payload.visibility)

    body = _decrypt_scribe_text(draft.content)

    note = PatientNote(
        organization_id=membership.organization_id,
        patient_id=encounter.patient_id,
        primary_service_id=service_id,
        encounter_id=encounter.id,
        status="draft",
        visibility=visibility,
        body=body,
        created_by_user_id=membership.user_id,
    )
    db.add(note)
    db.commit()
    db.refresh(note)

    log_event(
        db,
        action="scribe_inserted_into_chart",
        entity_type="patient_note",
        entity_id=note.id,
        organization_id=membership.organization_id,
        patient_id=note.patient_id,
        actor=membership.user.email,
        metadata={
            "capture_id": capture.id,
            "draft_id": draft.id,
            "note_type": draft.note_type,
            "encounter_id": encounter.id,
        },
    )

    return ScribeInsertIntoChartResponse(
        note_id=note.id,
        patient_id=note.patient_id,
        encounter_id=encounter.id,
        status=note.status,
    )
