# tests/test_nexus_codex_task_contract.py
"""
Phase 1 contract test: Nexus -> GitHub (issue + workflow dispatch) without touching GitHub.

Important:
- get_installation_token is called as get_installation_token(installation_id)
- Do NOT patch global httpx.Client.post (TestClient uses httpx internally)
- Patch ONLY nexus_codex.httpx and nexus_codex.get_installation_token
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@dataclass
class _FakeResponse:
    status_code: int
    _json: Optional[Dict[str, Any]] = None

    def json(self) -> Dict[str, Any]:
        return self._json or {}


class _FakeHTTPX:
    def __init__(self, calls: List[Dict[str, Any]]):
        self._calls = calls

    def post(self, url: str, **kwargs: Any) -> _FakeResponse:
        return self._capture_and_respond(url, **kwargs)

    class Client:
        def __init__(self, outer: "_FakeHTTPX", *args: Any, **kwargs: Any):
            self._outer = outer

        def __enter__(self) -> "_FakeHTTPX.Client":
            return self

        def __exit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
            return None

        def post(self, url: str, **kwargs: Any) -> _FakeResponse:
            return self._outer._capture_and_respond(url, **kwargs)

    def _capture_and_respond(self, url: str, **kwargs: Any) -> _FakeResponse:
        self._calls.append({"url": url, "kwargs": kwargs})

        # Only assert auth headers for GitHub URLs
        if "github" in url:
            headers = kwargs.get("headers") or {}
            assert "Authorization" in headers, "Expected Authorization header for GitHub calls"
            assert "test-token" in headers["Authorization"], "Expected mocked token to be used"

        if url.endswith("/repos/Tannrow/VEHR/issues"):
            issue_json = kwargs.get("json") or {}
            return _FakeResponse(
                201,
                {
                    "number": 123,
                    "html_url": "https://github.com/Tannrow/VEHR/issues/123",
                    "title": issue_json.get("title", ""),
                },
            )

        if url.endswith("/repos/Tannrow/VEHR/actions/workflows/codex_task.yml/dispatches"):
            return _FakeResponse(204, {})

        raise AssertionError(f"Unexpected URL called by nexus_codex: {url}")


def test_codex_task_contract_creates_issue_and_dispatches_workflow(monkeypatch: pytest.MonkeyPatch) -> None:
    app = create_app(enable_startup_validation=False)
    client = TestClient(app)

    endpoint = "/api/v1/api/dev/codex-task"

    payload = {
        "title": "Add health endpoint",
        "goal": "Create a task to add a health endpoint.",
        "risk": "low",
    }

    import app.api.v1.endpoints.nexus_codex as nexus_codex  # noqa: WPS433

    # FIX: real code calls get_installation_token(installation_id)
    monkeypatch.setattr(nexus_codex, "get_installation_token", lambda *_a, **_k: "test-token")

    calls: List[Dict[str, Any]] = []
    fake_httpx = _FakeHTTPX(calls)

    # Patch ONLY the module under test (won't affect TestClient)
    monkeypatch.setattr(nexus_codex, "httpx", fake_httpx)
    monkeypatch.setattr(fake_httpx, "Client", lambda *a, **k: _FakeHTTPX.Client(fake_httpx, *a, **k))

    resp = client.post(endpoint, json=payload)
    assert resp.status_code == 200, resp.text

    assert len(calls) == 2, f"Expected 2 GitHub calls, got {len(calls)}"
    issue_call = calls[0]
    dispatch_call = calls[1]

    assert issue_call["url"].endswith("/repos/Tannrow/VEHR/issues")
    issue_payload = issue_call["kwargs"].get("json") or {}

    assert isinstance(issue_payload.get("title"), str) and issue_payload["title"].strip()
    assert isinstance(issue_payload.get("body"), str) and issue_payload["body"].strip()

    labels = issue_payload.get("labels") or []
    assert "ai-task" in labels
    assert f"risk:{payload['risk']}" in labels

    assert dispatch_call["url"].endswith("/repos/Tannrow/VEHR/actions/workflows/codex_task.yml/dispatches")
    dispatch_payload = dispatch_call["kwargs"].get("json") or {}
    assert "ref" in dispatch_payload
    assert "inputs" in dispatch_payload and isinstance(dispatch_payload["inputs"], dict)

    inputs = dispatch_payload["inputs"]
    assert any(k in inputs for k in ("issue_number", "issue", "issue_id", "issueNumber")), (
        f"Expected issue identifier key in workflow inputs; got keys: {list(inputs.keys())}"
    )
