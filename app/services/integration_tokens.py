import base64
import hashlib
import os
from collections.abc import Iterable

from cryptography.fernet import Fernet


class TokenEncryptionError(RuntimeError):
    pass


DEFAULT_TOKEN_KEY_ENV = "INTEGRATION_TOKEN_KEY"


def _normalize_fernet_key(raw_key: str) -> bytes:
    raw_key = raw_key.strip()
    if not raw_key:
        raise TokenEncryptionError("Encryption key is missing")

    try:
        decoded = base64.urlsafe_b64decode(raw_key.encode("utf-8"))
        if len(decoded) == 32:
            return raw_key.encode("utf-8")
    except Exception:
        pass

    # Backward-compatible fallback: derive a stable 32-byte key from any secret string.
    derived = hashlib.sha256(raw_key.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(derived)


def _ordered_key_envs(
    *,
    key_env: str,
    fallback_env: str | None = None,
    legacy_envs: Iterable[str] | None = None,
) -> list[str]:
    ordered: list[str] = []
    for value in [key_env, fallback_env, *(legacy_envs or [])]:
        env_name = (value or "").strip()
        if env_name and env_name not in ordered:
            ordered.append(env_name)
    return ordered


def _load_raw_key(
    *,
    key_env: str,
    fallback_env: str | None = None,
) -> str:
    for env_name in _ordered_key_envs(key_env=key_env, fallback_env=fallback_env):
        candidate = os.getenv(env_name, "").strip()
        if candidate:
            return candidate

    if fallback_env:
        raise TokenEncryptionError(f"{key_env} and {fallback_env} are missing")
    raise TokenEncryptionError(f"{key_env} is missing")


def encrypt_token(
    token: str,
    *,
    key_env: str = DEFAULT_TOKEN_KEY_ENV,
    fallback_env: str | None = None,
) -> str:
    if not token:
        raise TokenEncryptionError("Token value is required")

    try:
        fernet = Fernet(_normalize_fernet_key(_load_raw_key(key_env=key_env, fallback_env=fallback_env)))
        return fernet.encrypt(token.encode("utf-8")).decode("utf-8")
    except TokenEncryptionError:
        raise
    except Exception as exc:
        raise TokenEncryptionError(f"Unable to encrypt token: {exc}") from exc


def decrypt_token(
    token_encrypted: str,
    *,
    key_env: str = DEFAULT_TOKEN_KEY_ENV,
    fallback_env: str | None = None,
    legacy_envs: Iterable[str] | None = None,
) -> str:
    if not token_encrypted:
        raise TokenEncryptionError("Encrypted token value is required")

    last_error: Exception | None = None
    attempted = False

    for env_name in _ordered_key_envs(
        key_env=key_env,
        fallback_env=fallback_env,
        legacy_envs=legacy_envs,
    ):
        raw_key = os.getenv(env_name, "").strip()
        if not raw_key:
            continue
        attempted = True

        try:
            fernet = Fernet(_normalize_fernet_key(raw_key))
            return fernet.decrypt(token_encrypted.encode("utf-8")).decode("utf-8")
        except Exception as exc:
            last_error = exc

    if attempted and last_error is not None:
        raise TokenEncryptionError(f"Unable to decrypt token: {last_error}") from last_error

    if fallback_env:
        raise TokenEncryptionError(f"{key_env} and {fallback_env} are missing")
    raise TokenEncryptionError(f"{key_env} is missing")
