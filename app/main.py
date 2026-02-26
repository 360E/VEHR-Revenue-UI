from __future__ import annotations

import logging
import os
import re
from typing import List, Optional

from fastapi import Request
from starlette.responses import Response

from app.create_app import create_app

logger = logging.getLogger("app.main")

# Required by tests: module-level ASGI app export
app = create_app()

# Required by tests
_EXPECTED_METHODS: List[str] = ["GET", "POST", "PATCH", "DELETE", "OPTIONS"]
_DEFAULT_ALLOWED_HEADERS: List[str] = ["Authorization", "Content-Type"]


def _truthy(val: Optional[str]) -> bool:
    return str(val).strip().lower() in {"1", "true", "yes", "y", "on"}


def _parse_csv(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [p.strip() for p in value.split(",") if p.strip()]


def _is_localhost_origin(origin: str) -> bool:
    # Matches http://localhost:3000 and http://127.0.0.1:3000 (+ any port)
    return bool(re.match(r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$", origin))


def get_cors_origins() -> List[str]:
    """
    Test contract:
    - reads CORS_ALLOWED_ORIGINS (CSV)
    - if LOCAL_DEV is truthy -> keep only localhost/127.0.0.1
    - returns sorted unique list (deterministic)
    """
    local_dev = _truthy(os.getenv("LOCAL_DEV"))
    origins = _parse_csv(os.getenv("CORS_ALLOWED_ORIGINS"))

    if local_dev:
        origins = [o for o in origins if _is_localhost_origin(o)]

    # Deterministic order; test expects 127.0.0.1 before localhost
    return sorted(set(origins))


def _is_preflight(request: Request) -> bool:
    return (
        request.method == "OPTIONS"
        and request.headers.get("origin") is not None
        and request.headers.get("access-control-request-method") is not None
    )


def _origin_allowed(origin: str) -> bool:
    # Exact match list for local/dev + configured allowed origins
    if origin in get_cors_origins():
        return True

    # Optional regex support for dynamic origins (won't affect your tests)
    pattern = (os.getenv("CORS_ORIGIN_REGEX") or "").strip()
    if pattern:
        try:
            return re.match(pattern, origin) is not None
        except re.error:
            return False

    return False


@app.middleware("http")
async def cors_preflight_logger_and_gate(request: Request, call_next):
    """
    Enforces preflight behavior required by tests:

    Allowed origin:
      - status 204 (or 200 also accepted by tests)
      - allow-origin = exact origin
      - allow-credentials = "true"
      - allow-methods includes GET, POST, PATCH, DELETE, OPTIONS
      - logs "cors_preflight_success" to logger "app.main"

    Disallowed origin:
      - status 400
      - no allow-origin header
      - logs "cors_preflight_failure" to logger "app.main"
    """
    if not _is_preflight(request):
        return await call_next(request)

    origin = request.headers.get("origin", "")

    if not _origin_allowed(origin):
        logger.warning("cors_preflight_failure origin=%s path=%s", origin, request.url.path)
        return Response(status_code=400)

    req_headers = request.headers.get("access-control-request-headers")
    allow_headers = req_headers or ", ".join(_DEFAULT_ALLOWED_HEADERS)

    resp = Response(status_code=204)
    resp.headers["Access-Control-Allow-Origin"] = origin
    resp.headers["Access-Control-Allow-Credentials"] = "true"
    resp.headers["Access-Control-Allow-Methods"] = ", ".join(_EXPECTED_METHODS)
    resp.headers["Access-Control-Allow-Headers"] = allow_headers
    resp.headers["Vary"] = "Origin"

    logger.info("cors_preflight_success origin=%s path=%s", origin, request.url.path)
    return resp
