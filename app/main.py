from __future__ import annotations

import os

from app.create_app import create_app, get_cors_origins


def _truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


enable_startup_validation = not _truthy(os.getenv("DISABLE_STARTUP_VALIDATION"))

app = create_app(enable_startup_validation=enable_startup_validation)

__all__ = ["app", "get_cors_origins"]