from __future__ import annotations

import time

from infrastructure.azure_client import AzureReliabilityClient


class _HttpError(Exception):
    def __init__(self, status_code: int) -> None:
        super().__init__("http")
        self.status_code = status_code


def test_wrapper_retries_429_then_succeeds(monkeypatch) -> None:
    client = AzureReliabilityClient()
    attempts = {"count": 0}
    sleeps: list[int] = []
    monkeypatch.setattr(time, "sleep", lambda seconds: sleeps.append(int(seconds)))

    def _operation() -> str:
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise _HttpError(429)
        return "ok"

    result = client.call(
        stage="openai_structuring",
        request_id="req-1",
        timeout_seconds=1,
        operation=_operation,
    )

    assert result.ok is True
    assert result.value == "ok"
    assert attempts["count"] == 3
    assert sleeps == [1, 2]


def test_wrapper_does_not_retry_400() -> None:
    client = AzureReliabilityClient()
    attempts = {"count": 0}

    def _operation() -> str:
        attempts["count"] += 1
        raise _HttpError(400)

    result = client.call(
        stage="document_intelligence_extract",
        request_id="req-2",
        timeout_seconds=1,
        operation=_operation,
    )

    assert result.ok is False
    assert result.error_code == "azure_invalid_response"
    assert attempts["count"] == 1

