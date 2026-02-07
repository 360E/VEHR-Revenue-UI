import os
from dataclasses import dataclass

import boto3
from botocore.config import Config


@dataclass(frozen=True)
class S3Settings:
    bucket: str
    region: str | None
    endpoint_url: str | None
    access_key_id: str
    secret_access_key: str
    use_path_style: bool
    presign_expires_seconds: int


def load_s3_settings() -> S3Settings:
    bucket = os.getenv("S3_BUCKET", "").strip()
    access_key_id = os.getenv("S3_ACCESS_KEY_ID", "").strip()
    secret_access_key = os.getenv("S3_SECRET_ACCESS_KEY", "").strip()
    if not bucket or not access_key_id or not secret_access_key:
        raise ValueError("S3_BUCKET, S3_ACCESS_KEY_ID, and S3_SECRET_ACCESS_KEY are required")

    region = os.getenv("S3_REGION", "").strip() or None
    endpoint_url = os.getenv("S3_ENDPOINT_URL", "").strip() or None
    use_path_style = os.getenv("S3_USE_PATH_STYLE", "").strip().lower() in {"1", "true", "yes"}
    presign_expires_seconds = int(os.getenv("S3_PRESIGN_EXPIRES_SECONDS", "900"))

    return S3Settings(
        bucket=bucket,
        region=region,
        endpoint_url=endpoint_url,
        access_key_id=access_key_id,
        secret_access_key=secret_access_key,
        use_path_style=use_path_style,
        presign_expires_seconds=presign_expires_seconds,
    )


def get_s3_client(settings: S3Settings):
    config = None
    if settings.use_path_style:
        config = Config(s3={"addressing_style": "path"})

    return boto3.client(
        "s3",
        region_name=settings.region,
        endpoint_url=settings.endpoint_url,
        aws_access_key_id=settings.access_key_id,
        aws_secret_access_key=settings.secret_access_key,
        config=config,
    )


def upload_fileobj(
    client,
    bucket: str,
    key: str,
    fileobj,
    content_type: str | None = None,
) -> None:
    extra_args = {}
    if content_type:
        extra_args["ContentType"] = content_type
    if extra_args:
        client.upload_fileobj(fileobj, bucket, key, ExtraArgs=extra_args)
    else:
        client.upload_fileobj(fileobj, bucket, key)


def generate_presigned_get_url(
    client,
    bucket: str,
    key: str,
    expires_in: int,
    filename: str | None = None,
) -> str:
    params = {"Bucket": bucket, "Key": key}
    if filename:
        params["ResponseContentDisposition"] = f'attachment; filename="{filename}"'
    return client.generate_presigned_url(
        "get_object",
        Params=params,
        ExpiresIn=expires_in,
    )
