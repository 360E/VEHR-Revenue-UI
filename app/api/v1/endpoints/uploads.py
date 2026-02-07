import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.services.s3_presign import (
    generate_presigned_get_url,
    generate_presigned_put_url,
    get_presign_s3_client,
    load_presign_s3_settings,
)


router = APIRouter(tags=["Uploads"])


class PresignUploadRequest(BaseModel):
    filename: str = Field(min_length=1, max_length=255)
    content_type: Literal["application/pdf", "image/png", "image/jpeg"]


class PresignUploadResponse(BaseModel):
    key: str
    url: str
    method: str
    headers: dict[str, str]


class PresignDownloadResponse(BaseModel):
    url: str


def _sanitize_filename(filename: str) -> str:
    safe_name = Path(filename).name
    safe_name = re.sub(r"[^A-Za-z0-9._-]", "_", safe_name)
    if not safe_name:
        return "file"
    return safe_name[:180]


def _build_upload_key(filename: str) -> str:
    now = datetime.now(timezone.utc)
    safe_name = _sanitize_filename(filename)
    return f"uploads/{now:%Y/%m}/{uuid4()}_{safe_name}"


@router.post("/uploads/presign", response_model=PresignUploadResponse)
def create_presigned_upload(payload: PresignUploadRequest) -> PresignUploadResponse:
    try:
        settings = load_presign_s3_settings()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    key = _build_upload_key(payload.filename)
    client = get_presign_s3_client(settings)

    try:
        url = generate_presigned_put_url(
            client=client,
            bucket=settings.bucket,
            key=key,
            content_type=payload.content_type,
            expires_in=settings.expires_in_seconds,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to generate upload URL",
        ) from exc

    return PresignUploadResponse(
        key=key,
        url=url,
        method="PUT",
        headers={"Content-Type": payload.content_type},
    )


@router.get("/uploads/{key:path}/download", response_model=PresignDownloadResponse)
def create_presigned_download(key: str) -> PresignDownloadResponse:
    key = key.lstrip("/")
    if not key or not key.startswith("uploads/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid key",
        )

    try:
        settings = load_presign_s3_settings()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(exc),
        ) from exc

    client = get_presign_s3_client(settings)

    try:
        url = generate_presigned_get_url(
            client=client,
            bucket=settings.bucket,
            key=key,
            expires_in=settings.expires_in_seconds,
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to generate download URL",
        ) from exc

    return PresignDownloadResponse(url=url)
