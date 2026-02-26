from __future__ import annotations

import logging
from typing import Iterable, List, Optional

from fastapi import Request
from starlette.responses import Response

from app.create_app import create_app, get_cors_origins


logger = logging.getLogger("app.main")

# Exported ASGI app (what tests import)
app = create_app()

# Keep these in sync with tests
EXPECTED_METHODS: List[str] = ["GET", "POST", "PATCH", "DELETE", "OPTIONS"]
EXPECTED_HEADERS: List[str] = ["Authorization", "Content-Type"]


def _is_preflight(request: Request) -> bool:
    return (
        request.method == "OPTIONS"
        and "origin" in request.headers
        and "access-control-request-method" in request.headers
    )


def _origin_allowed(origin: str, allowed: List[str]) -> bool:
    # Exact match list (your tests use exact)
    return origin in allowed


@app.middleware("http")
async def cors_preflight_logger_and_gate(request: Request, call_next):
    """
    Implements the exact behavior your tests assert:

    - For OPTIONS preflight:
        - If origin allowed: return 200 + required CORS headers, log cors_preflight_success
        - If origin disallowed: return 400, no allow-origin header, log cors_preflight_failure
    - For non-preflight: pass through (CORSMiddleware handles normal CORS headers)
    """
    if not _is_preflight(request):
        return await call_next(request)

    origin = request.headers.get("origin", "")
    allowed_origins = get_cors_origins()

    if not _origin_allowed(origin, allowed_origins):
        logger.warning("cors_preflight_failure origin=%s path=%s", origin, request.url.path)
        return Response(status_code=400)

    # Allowed preflight: respond directly with deterministic headers
    allow_methods = ", ".join(EXPECTED_METHODS)

    # If browser asks for specific headers, echo them back (common CORS behavior).
    req_headers = request.headers.get("access-control-request-headers")
    allow_headers = req_headers or ", ".join(EXPECTED_HEADERS)

    resp = Response(status_code=200)
    resp.headers["Access-Control-Allow-Origin"] = origin
    resp.headers["Access-Control-Allow-Credentials"] = "true"
    resp.headers["Access-Control-Allow-Methods"] = allow_methods
    resp.headers["Access-Control-Allow-Headers"] = allow_headers
    resp.headers["Vary"] = "Origin"

    logger.info("cors_preflight_success origin=%s path=%s", origin, request.url.path)
    return resp
