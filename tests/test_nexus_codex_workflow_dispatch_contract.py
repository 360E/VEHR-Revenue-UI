from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
import app.api.v1.endpoints.nexus_codex as nexus_codex


def _workflow_expected_inputs() -> Dict[str, dict]:
    """
    Parse .github/workflows/codex_task.yml and extract workflow_dispatch.inputs
    without extra dependencies.
    """
    yml = Path(".github/workflows/codex_task.yml").read_text(encoding="utf-8").splitlines()

    wd_i = next((i for i, line in enumerate(yml) if re.match(r"^\s*workflow_dispatch:\s*$", line)), None)
    if wd_i is None:
        raise AssertionError("codex_task.yml missing 'workflow_dispatch:'")

    inputs_i = None
    for i in range(wd_i + 1, min(wd_i + 200, len(yml))):
        if re.match(r"^\s*inputs:\s*$", yml[i]):
            inputs_i = i
            break
    if inputs_i is None:
        raise AssertionError("codex_task.yml missing 'workflow_dispatch: inputs:'")

    expected: Dict[str, dict] = {}
    i = inputs_i + 1
    while i < len(yml):
        line = yml[i]

        # stop when block ends (dedent to <= 3 spaces or a top-level key)
        if re.match(r"^\S", line) or re.match(r"^\s{0,3}\S", line):
            break

        m_key = re.match(r"^\s{6}([a-zA-Z0-9_]+):\s*$", line)
        if m_key:
            key = m_key.group(1)
            spec = {"required": False, "default": None}
            j = i + 1
            while j < len(yml):
                sub = yml[j]
                if re.match(r"^\s{6}[a-zA-Z0-9_]+:\s*$", sub):
                    break
                if re.match(r"^\S", sub) or re.match(r"^\s{0,3}\S", sub):
                    break
                m_req = re.match(r"^\s{8}required:\s*(true|false)\s*$", sub)
                if m_req:
                    spec["required"] = (m_req.group(1) == "true")
                m_def = re.match(r"^\s{8}default:\s*\"?([^\"]+)\"?\s*$", sub)
                if m_def:
                    spec["default"] = m_def.group(1)
                j += 1
            expected[key] = spec
        i += 1

    if not expected:
        raise AssertionError("Could not parse any workflow_dispatch input keys from codex_task.yml")

    return expected


class _RecorderHTTPX:
    """
    Fake httpx used ONLY by app.api.v1.endpoints.nexus_codex.
    Captures POST requests and returns minimal GitHub-like responses.
    """
    def __init__(self) -> None:
        self.posts: List[Dict[str, Any]] = []

    def post(self, url: str, *args: Any, **kwargs: Any) -> Any:
        self.posts.append({"url": url, "args": args, "kwargs": kwargs})

        class _Resp:
            def __init__(self, url: str) -> None:
                self._url = url
                # Issue create is 201; dispatch is 204; but we can be permissive.
                self.status_code = 201

            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict:
                # Simulate GitHub issue create response
                if "/issues" in self._url and "/dispatches" not in self._url:
                    return {
                        "number": 123,
                        "html_url": "https://github.com/org/repo/issues/123",
                    }
                # Simulate dispatch response body (usually empty)
                return {}

            @property
            def text(self) -> str:
                return ""

        return _Resp(url)


def _find_dispatch_payload(posts: List[Dict[str, Any]]) -> Dict[str, Any]:
    for p in posts:
        if "/dispatches" in p["url"]:
            j = p["kwargs"].get("json")
            if isinstance(j, dict):
                return j
    raise AssertionError(f"No workflow dispatch call captured. URLs: {[p['url'] for p in posts]}")


def test_workflow_dispatch_inputs_match_codex_task_yml(monkeypatch: pytest.MonkeyPatch) -> None:
    app = create_app(enable_startup_validation=False)
    client = TestClient(app)

    monkeypatch.setattr(nexus_codex, "get_installation_token", lambda *_a, **_k: "test-token")

    recorder = _RecorderHTTPX()
    monkeypatch.setattr(nexus_codex, "httpx", recorder)

    resp = client.post(
        "/api/v1/api/dev/codex-task",
        json={"title": "Contract test", "goal": "Verify workflow_dispatch inputs contract"},
    )
    assert resp.status_code in (200, 201), resp.text

    dispatch = _find_dispatch_payload(recorder.posts)
    assert "inputs" in dispatch and isinstance(dispatch["inputs"], dict), f"Dispatch payload missing inputs: {dispatch}"

    actual_inputs = dispatch["inputs"]

    expected = _workflow_expected_inputs()
    expected_keys = set(expected.keys())
    actual_keys = set(actual_inputs.keys())

    assert actual_keys == expected_keys, (
        "workflow_dispatch inputs keys mismatch\n"
        f"Expected: {sorted(expected_keys)}\n"
        f"Actual:   {sorted(actual_keys)}\n"
        f"Dispatch inputs: {actual_inputs}"
    )

    for key, spec in expected.items():
        if spec.get("required"):
            val = actual_inputs.get(key)
            assert val is not None, f"Required input '{key}' missing"
            if isinstance(val, str):
                assert val.strip() != "", f"Required input '{key}' empty"

