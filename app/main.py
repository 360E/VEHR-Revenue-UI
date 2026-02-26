"""
Entry-point module.

Tests import `create_app` from here:
    from app.main import create_app

Gunicorn can target:
    app.main:app
or:
    app.main:create_app()
"""

from __future__ import annotations

from app.create_app import create_app

# Create a default app instance for WSGI servers that expect "app"
app = create_app()
