from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
from dataclasses import dataclass
from typing import Any, Callable, Generic, Literal, TypeVar


AzureErrorCode = Literal[
    "azure_timeout",
    "azure_rate_limited",
    "azure_unavailable",
    "azure_invalid_response",
    "azure_auth_failure",
]

_BACKOFF_SECONDS = (1, 2, 4)
_RETRYABLE_STATUS_CODES = {429, 503}
_NON_RETRYABLE_STATUS_CODES = {400, 401, 403, 422}
_TRANSIENT_NETWORK_TOKENS = ("connection", "network", "transport", "socket")

logger = logging.getLogger(__name__)

T = TypeVar("T")


@dataclass(frozen=True)
class AzureCallResult(Generic[T]):
    ok: bool
    value: T | None
    error_code: AzureErrorCode | None
    request_id: str
    duration_ms: int


class AzureClientError(Exception):
    def __init__(self, *, stage: str, error_code: AzureErrorCode, request_id: str) -> None:
        super().__init__(stage)
        self.stage = stage
        self.error_code = error_code
        self.request_id = request_id


class AzureReliabilityClient:
    def call(
        self,
        *,
        stage: str,
        request_id: str,
        timeout_seconds: float,
        operation: Callable[[], T],
    ) -> AzureCallResult[T]:
        started = time.perf_counter()
        error_code: AzureErrorCode | None = None
        for attempt, backoff in enumerate(_BACKOFF_SECONDS, start=1):
            try:
                value = self._run_with_timeout(operation, timeout_seconds=timeout_seconds)
                duration_ms = int((time.perf_counter() - started) * 1000)
                self._log(stage=stage, request_id=request_id, duration_ms=duration_ms, success=True, error_code=None)
                return AzureCallResult(
                    ok=True,
                    value=value,
                    error_code=None,
                    request_id=request_id,
                    duration_ms=duration_ms,
                )
            except Exception as exc:  # noqa: BLE001
                error_code = self._map_error_code(exc)
                if attempt < len(_BACKOFF_SECONDS) and self._should_retry(exc, error_code=error_code):
                    time.sleep(backoff)
                    continue
                break

        duration_ms = int((time.perf_counter() - started) * 1000)
        self._log(stage=stage, request_id=request_id, duration_ms=duration_ms, success=False, error_code=error_code)
        return AzureCallResult(
            ok=False,
            value=None,
            error_code=error_code or "azure_unavailable",
            request_id=request_id,
            duration_ms=duration_ms,
        )

    def _run_with_timeout(self, operation: Callable[[], T], *, timeout_seconds: float) -> T:
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(operation)
            try:
                return future.result(timeout=timeout_seconds)
            except (FuturesTimeoutError, TimeoutError) as exc:
                raise TimeoutError() from exc

    def _status_code(self, exc: Exception) -> int | None:
        for attr in ("status_code",):
            status = getattr(exc, attr, None)
            if isinstance(status, int):
                return status
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
        return status if isinstance(status, int) else None

    def _map_error_code(self, exc: Exception) -> AzureErrorCode:
        if isinstance(exc, TimeoutError):
            return "azure_timeout"
        status_code = self._status_code(exc)
        if status_code == 429:
            return "azure_rate_limited"
        if status_code in {401, 403}:
            return "azure_auth_failure"
        if status_code == 400:
            return "azure_invalid_response"
        if status_code == 503:
            return "azure_unavailable"
        name = exc.__class__.__name__.lower()
        module = exc.__class__.__module__.lower()
        if "authentication" in name or "credential" in name:
            return "azure_auth_failure"
        if any(token in name or token in module for token in _TRANSIENT_NETWORK_TOKENS):
            return "azure_unavailable"
        return "azure_unavailable"

    def _should_retry(self, exc: Exception, *, error_code: AzureErrorCode) -> bool:
        if error_code == "azure_timeout":
            return False
        status_code = self._status_code(exc)
        if status_code in _NON_RETRYABLE_STATUS_CODES:
            return False
        if status_code in _RETRYABLE_STATUS_CODES:
            return True
        name = exc.__class__.__name__.lower()
        module = exc.__class__.__module__.lower()
        return any(token in name or token in module for token in _TRANSIENT_NETWORK_TOKENS)

    def _log(
        self,
        *,
        stage: str,
        request_id: str,
        duration_ms: int,
        success: bool,
        error_code: AzureErrorCode | None,
    ) -> None:
        logger.info(
            "azure_call_complete",
            extra={
                "event": "azure_call_complete",
                "stage": stage,
                "duration_ms": duration_ms,
                "success": bool(success),
                "error_code": error_code,
                "request_id": request_id,
            },
        )
