from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import msal
import requests
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.user_microsoft_connection import UserMicrosoftConnection
from app.services.integration_tokens import TokenEncryptionError, decrypt_token, encrypt_token


GRAPH_BASE_URL = "https://graph.microsoft.com/v1.0"
DEFAULT_DELEGATED_SCOPES = "offline_access Tasks.ReadWrite Calendars.ReadWrite User.Read"


class MicrosoftGraphClientError(RuntimeError):
    def __init__(self, detail: str, status_code: int = 502) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


class MicrosoftGraphNotConnectedError(MicrosoftGraphClientError):
    def __init__(self) -> None:
        super().__init__("Microsoft integration is not connected for this user", status_code=409)


class MicrosoftGraphConfigurationError(MicrosoftGraphClientError):
    def __init__(self, detail: str) -> None:
        super().__init__(detail, status_code=500)


@dataclass(frozen=True)
class MicrosoftDelegatedAuthConfig:
    client_id: str
    client_secret: str
    redirect_uri: str
    scopes: list[str]

def _required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise MicrosoftGraphConfigurationError(f"{name} is not configured")
    return value


def _split_scopes(raw: str) -> list[str]:
    scopes = [item.strip() for item in (raw or "").split() if item.strip()]
    # Preserve order but drop duplicates.
    ordered: list[str] = []
    for scope in scopes:
        if scope not in ordered:
            ordered.append(scope)
    return ordered


def load_delegated_auth_config_from_env() -> MicrosoftDelegatedAuthConfig:
    client_id = os.getenv("MS_GRAPH_CLIENT_ID", "").strip() or os.getenv("MS_CLIENT_ID", "").strip()
    if not client_id:
        raise MicrosoftGraphConfigurationError("MS_CLIENT_ID is not configured")
    client_secret = os.getenv("MS_GRAPH_CLIENT_SECRET", "").strip() or os.getenv("MS_CLIENT_SECRET", "").strip()
    if not client_secret:
        raise MicrosoftGraphConfigurationError("MS_CLIENT_SECRET is not configured")
    redirect_uri = os.getenv("MS_GRAPH_REDIRECT_URI", "").strip() or os.getenv("MS_REDIRECT_URI", "").strip()
    if not redirect_uri:
        raise MicrosoftGraphConfigurationError("MS_REDIRECT_URI is not configured")

    scopes_raw = (
        os.getenv("MS_GRAPH_SCOPES_DELEGATED", "").strip()
        or os.getenv("MS_GRAPH_SCOPES", "").strip()
        or DEFAULT_DELEGATED_SCOPES
    )
    scopes = _split_scopes(scopes_raw)
    if not scopes:
        raise MicrosoftGraphConfigurationError("MS_GRAPH_SCOPES_DELEGATED is empty")

    return MicrosoftDelegatedAuthConfig(
        client_id=client_id,
        client_secret=client_secret,
        redirect_uri=redirect_uri,
        scopes=scopes,
    )

def _authority_for_tenant(tenant_id: str) -> str:
    tenant = (tenant_id or "").strip() or "common"
    return f"https://login.microsoftonline.com/{tenant}"


def build_confidential_client_application(
    *,
    config: MicrosoftDelegatedAuthConfig,
    tenant_id: str,
    token_cache: msal.SerializableTokenCache | None = None,
) -> msal.ConfidentialClientApplication:
    return msal.ConfidentialClientApplication(
        client_id=config.client_id,
        authority=_authority_for_tenant(tenant_id),
        client_credential=config.client_secret,
        token_cache=token_cache,
    )


def _connection_for_user(*, db: Session, organization_id: str, user_id: str) -> UserMicrosoftConnection:
    row = db.execute(
        select(UserMicrosoftConnection).where(
            UserMicrosoftConnection.organization_id == organization_id,
            UserMicrosoftConnection.user_id == user_id,
        )
    ).scalar_one_or_none()
    if not row or not (row.token_cache_encrypted or "").strip():
        raise MicrosoftGraphNotConnectedError()
    return row


def load_token_cache(
    *,
    db: Session,
    organization_id: str,
    user_id: str,
) -> tuple[msal.SerializableTokenCache, UserMicrosoftConnection]:
    connection = _connection_for_user(db=db, organization_id=organization_id, user_id=user_id)
    cache = msal.SerializableTokenCache()
    try:
        decrypted = decrypt_token(connection.token_cache_encrypted, key_env="INTEGRATION_TOKEN_KEY")
    except TokenEncryptionError as exc:
        raise MicrosoftGraphClientError("Stored Microsoft token cache could not be decrypted", status_code=500) from exc

    try:
        cache.deserialize(decrypted)
    except Exception as exc:
        raise MicrosoftGraphClientError("Stored Microsoft token cache is invalid", status_code=500) from exc

    return cache, connection


def save_token_cache(
    *,
    db: Session,
    connection: UserMicrosoftConnection,
    cache: msal.SerializableTokenCache,
) -> None:
    serialized = cache.serialize()
    try:
        encrypted = encrypt_token(serialized, key_env="INTEGRATION_TOKEN_KEY")
    except TokenEncryptionError as exc:
        raise MicrosoftGraphClientError("Unable to encrypt Microsoft token cache", status_code=500) from exc

    connection.token_cache_encrypted = encrypted
    db.add(connection)
    db.commit()


def acquire_graph_token(
    *,
    db: Session,
    organization_id: str,
    user_id: str,
    scopes: list[str] | None = None,
    force_refresh: bool = False,
) -> str:
    config = load_delegated_auth_config_from_env()
    requested_scopes = scopes or config.scopes
    cache, connection = load_token_cache(db=db, organization_id=organization_id, user_id=user_id)

    app = build_confidential_client_application(
        config=config,
        tenant_id=connection.tenant_id,
        token_cache=cache,
    )
    accounts = app.get_accounts()
    if not accounts:
        raise MicrosoftGraphNotConnectedError()

    account = accounts[0]
    if connection.msft_user_id:
        match = next(
            (row for row in accounts if str(row.get("local_account_id", "")).strip() == connection.msft_user_id),
            None,
        )
        if match is not None:
            account = match

    result = app.acquire_token_silent(requested_scopes, account=account, force_refresh=force_refresh)
    if not result:
        raise MicrosoftGraphNotConnectedError()
    if "error" in result:
        detail = str(result.get("error_description") or result.get("error") or "microsoft_auth_failed").strip()
        raise MicrosoftGraphClientError(detail, status_code=401)

    access_token = str(result.get("access_token", "")).strip()
    if not access_token:
        raise MicrosoftGraphClientError("Microsoft token response missing access_token", status_code=502)

    if getattr(cache, "has_state_changed", False):
        save_token_cache(db=db, connection=connection, cache=cache)

    return access_token


def _parse_graph_error(body: Any, status_code: int) -> str:
    if isinstance(body, dict):
        error_value = body.get("error")
        if isinstance(error_value, dict):
            code = str(error_value.get("code", "")).strip()
            message = str(error_value.get("message", "")).strip()
            if code and message:
                return f"{code}: {message}"
            if message:
                return message
        if isinstance(error_value, str) and error_value.strip():
            return error_value.strip()

    if status_code == 401:
        return "Microsoft Graph authorization failed"
    return f"Microsoft Graph request failed with status {status_code}"


def graph_request(
    method: str,
    path: str,
    token: str,
    *,
    json_body: dict[str, Any] | None = None,
    params: dict[str, str] | None = None,
    timeout_seconds: float = 20.0,
) -> dict[str, Any]:
    target_url = f"{GRAPH_BASE_URL}/{path.lstrip('/')}"
    headers = {"Authorization": f"Bearer {token}"}
    try:
        response = requests.request(
            method.upper(),
            target_url,
            headers=headers,
            json=json_body,
            params=params,
            timeout=timeout_seconds,
        )
    except requests.RequestException as exc:
        raise MicrosoftGraphClientError("Microsoft Graph request failed", status_code=502) from exc

    body: Any = {}
    try:
        body = response.json()
    except Exception:
        body = {}

    if response.status_code >= 400:
        detail = _parse_graph_error(body, response.status_code)
        if response.status_code in {400, 401, 403, 404, 409}:
            raise MicrosoftGraphClientError(detail, status_code=response.status_code)
        raise MicrosoftGraphClientError(detail, status_code=502)

    if not isinstance(body, dict):
        raise MicrosoftGraphClientError("Unexpected Microsoft Graph response format", status_code=502)
    return body
