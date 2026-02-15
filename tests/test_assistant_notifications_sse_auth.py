from __future__ import annotations

import asyncio
from types import SimpleNamespace
from urllib.parse import urlencode

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker
from starlette.requests import Request

from app.api.v1.endpoints.ai_copilot import stream_assistant_notifications
from app.core.deps import get_current_membership_sse
from app.core.rbac import ROLE_ADMIN
from app.core.security import create_access_token, hash_password
from app.core.time import utc_now
from app.db.base import Base
from app.db.models.assistant_notification import AssistantNotification
from app.db.models.organization import Organization
from app.db.models.organization_membership import OrganizationMembership
from app.db.models.user import User
from app.main import get_cors_origins


def _setup_db(tmp_path):
    database_file = tmp_path / "assistant_sse.sqlite"
    engine = create_engine(
        f"sqlite:///{database_file}",
        connect_args={"check_same_thread": False},
    )
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    from app.db import models as _models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    return engine, TestingSessionLocal


def _seed_user_membership(session_factory):
    with session_factory() as db:
        org = Organization(name="Assistant SSE Org")
        db.add(org)
        db.flush()

        user = User(
            email="assistant-sse@example.com",
            full_name="Assistant SSE User",
            hashed_password=hash_password("TestPass123!"),
            is_active=True,
        )
        db.add(user)
        db.flush()

        membership = OrganizationMembership(
            organization_id=org.id,
            user_id=user.id,
            role=ROLE_ADMIN,
        )
        db.add(membership)
        db.commit()

        token = create_access_token({"sub": user.id, "org_id": org.id})
        return token, org.id, user.id


def _make_request(*, cookie: str | None = None, query: str | None = None) -> Request:
    headers: list[tuple[bytes, bytes]] = []
    if cookie:
        headers.append((b"cookie", cookie.encode("utf-8")))

    scope = {
        "type": "http",
        "asgi": {"spec_version": "2.3"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/api/v1/ai/notifications/stream",
        "raw_path": b"/api/v1/ai/notifications/stream",
        "query_string": (query or "").encode("utf-8"),
        "headers": headers,
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
        "state": {},
    }
    return Request(scope)


def test_get_current_membership_sse_accepts_authorization_header(tmp_path) -> None:
    engine, session_factory = _setup_db(tmp_path)
    try:
        token, _org_id, user_id = _seed_user_membership(session_factory)
        request = _make_request()
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)

        with session_factory() as db:
            membership = get_current_membership_sse(request=request, credentials=creds, db=db)
            assert membership.user_id == user_id
            assert getattr(request.state, "sse_auth_source", None) == "authorization"
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_get_current_membership_sse_accepts_cookie_token(tmp_path) -> None:
    engine, session_factory = _setup_db(tmp_path)
    try:
        token, _org_id, user_id = _seed_user_membership(session_factory)
        request = _make_request(cookie=f"vehr_access_token={token}")

        with session_factory() as db:
            membership = get_current_membership_sse(request=request, credentials=None, db=db)
            assert membership.user_id == user_id
            assert getattr(request.state, "sse_auth_source", None) == "cookie"
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_get_current_membership_sse_rejects_missing_token(tmp_path) -> None:
    engine, session_factory = _setup_db(tmp_path)
    try:
        _seed_user_membership(session_factory)
        request = _make_request()

        with session_factory() as db:
            with pytest.raises(HTTPException) as excinfo:
                get_current_membership_sse(request=request, credentials=None, db=db)
            assert excinfo.value.status_code == 401
            assert excinfo.value.detail == "Missing credentials"
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_get_current_membership_sse_rejects_query_token_by_default(tmp_path) -> None:
    engine, session_factory = _setup_db(tmp_path)
    try:
        token, _org_id, _user_id = _seed_user_membership(session_factory)
        request = _make_request(query=urlencode({"access_token": token}))

        with session_factory() as db:
            with pytest.raises(HTTPException) as excinfo:
                get_current_membership_sse(request=request, credentials=None, db=db)
            assert excinfo.value.status_code == 400
            assert excinfo.value.detail == "query_token_not_allowed"
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_get_current_membership_sse_allows_query_token_compat_when_enabled(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("FEATURE_SSE_QUERY_TOKEN_COMPAT", "true")
    engine, session_factory = _setup_db(tmp_path)
    try:
        token, _org_id, user_id = _seed_user_membership(session_factory)
        request = _make_request(query=urlencode({"access_token": token}))

        with session_factory() as db:
            membership = get_current_membership_sse(request=request, credentials=None, db=db)
            assert membership.user_id == user_id
            assert getattr(request.state, "sse_auth_source", None) == "query_param"
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_notifications_stream_yields_event_and_sets_sse_headers(tmp_path) -> None:
    engine, session_factory = _setup_db(tmp_path)
    try:
        token, org_id, user_id = _seed_user_membership(session_factory)
        auth_request = _make_request(cookie=f"vehr_access_token={token}")

        class FakeRequest:
            def __init__(self) -> None:
                self._calls = 0
                self.state = SimpleNamespace(sse_auth_source="cookie")

            async def is_disconnected(self) -> bool:
                self._calls += 1
                return self._calls > 1

        with session_factory() as db:
            membership = get_current_membership_sse(request=auth_request, credentials=None, db=db)
            db.add(
                AssistantNotification(
                    organization_id=org_id,
                    user_id=user_id,
                    reminder_id=None,
                    type="reminder",
                    title="Test reminder",
                    body="Test body",
                    channel="in_chat",
                    due_at=utc_now(),
                    attempt=0,
                    delivery_targets={"in_chat": True},
                )
            )
            db.commit()

            response = asyncio.run(
                stream_assistant_notifications(
                    request=FakeRequest(),
                    membership=membership,
                    db=db,
                )
            )
            assert response.status_code == 200
            assert response.media_type == "text/event-stream"
            assert response.headers.get("Cache-Control") == "no-cache"
            assert response.headers.get("Connection") == "keep-alive"
            assert response.headers.get("X-Accel-Buffering") == "no"

            chunk = asyncio.run(response.body_iterator.__anext__())
            chunk_text = chunk.decode() if isinstance(chunk, bytes) else str(chunk)
            assert "event: notification" in chunk_text
            asyncio.run(response.body_iterator.aclose())
    finally:
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_get_cors_origins_never_returns_wildcard_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", "*")
    origins = get_cors_origins()
    assert "*" not in origins

