import os
from dataclasses import dataclass

import boto3


@dataclass(frozen=True)
class PresignS3Settings:
    region: str
    bucket: str
    access_key_id: str
    secret_access_key: str
    expires_in_seconds: int


def load_presign_s3_settings() -> PresignS3Settings:
    region = os.getenv("AWS_REGION", "").strip()
    bucket = os.getenv("S3_BUCKET_NAME", "").strip()
    access_key_id = os.getenv("AWS_ACCESS_KEY_ID", "").strip()
    secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY", "").strip()
    expires_raw = os.getenv("S3_PRESIGN_EXPIRES_SECONDS", "900").strip()

    missing = [
        name
        for name, value in (
            ("AWS_REGION", region),
            ("S3_BUCKET_NAME", bucket),
            ("AWS_ACCESS_KEY_ID", access_key_id),
            ("AWS_SECRET_ACCESS_KEY", secret_access_key),
        )
        if not value
    ]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    try:
        expires_in_seconds = int(expires_raw)
    except ValueError as exc:
        raise ValueError("S3_PRESIGN_EXPIRES_SECONDS must be an integer") from exc
    if expires_in_seconds <= 0:
        raise ValueError("S3_PRESIGN_EXPIRES_SECONDS must be greater than 0")

    return PresignS3Settings(
        region=region,
        bucket=bucket,
        access_key_id=access_key_id,
        secret_access_key=secret_access_key,
        expires_in_seconds=expires_in_seconds,
    )


def get_presign_s3_client(settings: PresignS3Settings):
    return boto3.client(
        "s3",
        region_name=settings.region,
        aws_access_key_id=settings.access_key_id,
        aws_secret_access_key=settings.secret_access_key,
    )


def generate_presigned_put_url(
    client,
    bucket: str,
    key: str,
    content_type: str,
    expires_in: int,
) -> str:
    return client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": bucket,
            "Key": key,
            "ContentType": content_type,
        },
        ExpiresIn=expires_in,
        HttpMethod="PUT",
    )


def generate_presigned_get_url(
    client,
    bucket: str,
    key: str,
    expires_in: int,
) -> str:
    return client.generate_presigned_url(
        "get_object",
        Params={
            "Bucket": bucket,
            "Key": key,
        },
        ExpiresIn=expires_in,
        HttpMethod="GET",
    )
