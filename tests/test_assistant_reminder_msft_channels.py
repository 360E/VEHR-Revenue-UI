from __future__ import annotations

from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.rbac import ROLE_ADMIN
from app.core.security import create_access_token, hash_password
from app.core.time import utc_now
from app.db.base import Base
from app.db.models.assistant_reminder import AssistantReminder
from app.db.models.audit_event import AuditEvent
from app.db.models.organization import Organization
from app.db.models.organization_membership import OrganizationMembership
from app.db.models.user import User
from app.db.session import get_db
from app.main import app
from app.services import microsoft_graph
from app.workers.reminder_dispatcher import retry_pending_msft_channels


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _build_session(tmp_path):
    database_file = tmp_path / "assistant_reminders_msft.sqlite"
    engine = create_engine(
        f"sqlite:///{database_file}",
        connect_args={"check_same_thread": False},
    )
    testing_session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    from app.db import models as _models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return engine, testing_session_local


def _seed_admin_token(session_factory) -> tuple[str, str, str]:
    with session_factory() as db:
        org = Organization(name="Assistant Reminder MSFT Org")
        db.add(org)
        db.flush()

        user = User(
            email="assistant-reminder@example.com",
            full_name="Assistant Reminder User",
            hashed_password=hash_password("TestPass123!"),
            is_active=True,
        )
        db.add(user)
        db.flush()

        db.add(
            OrganizationMembership(
                organization_id=org.id,
                user_id=user.id,
                role=ROLE_ADMIN,
            )
        )
        db.commit()

        token = create_access_token({"sub": user.id, "org_id": org.id})
        return token, org.id, user.id


def test_channel_selection_due_at_with_time_creates_outlook_event(tmp_path, monkeypatch) -> None:
    engine, session_factory = _build_session(tmp_path)
    try:
        token, _org_id, _user_id = _seed_admin_token(session_factory)

        def fake_create_event(*, db, organization_id, user_id, subject, body, start_datetime, end_datetime, time_zone, transaction_id=None):  # noqa: ANN001
            assert subject == "Valley AI Reminder"
            assert body == "Open VEHR to view details."
            assert time_zone
            assert transaction_id
            return "evt-123"

        def fake_create_task(*args, **kwargs):  # noqa: ANN001
            raise AssertionError("To Do should not be called for time-specific reminders")

        monkeypatch.setattr(microsoft_graph, "create_outlook_event_draft", fake_create_event)
        monkeypatch.setattr(microsoft_graph, "create_todo_task_draft", fake_create_task)

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/ai/reminders",
                headers=_auth_header(token),
                json={
                    "title": "Follow up",
                    "due_at": "2026-02-16T15:00:00Z",
                },
            )
            assert response.status_code == 201
            body = response.json()
            assert body["channels"]["in_chat"] is True
            assert body["channels"]["outlook"] is True
            assert body.get("channels", {}).get("todo") in {None, False}
            assert body["msft_event_id"] == "evt-123"
            assert body["warnings"] == []
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_channel_selection_date_only_creates_todo_task(tmp_path, monkeypatch) -> None:
    engine, session_factory = _build_session(tmp_path)
    try:
        token, _org_id, _user_id = _seed_admin_token(session_factory)

        def fake_create_task(*, db, organization_id, user_id, list_name, title, body, due_datetime, time_zone):  # noqa: ANN001
            assert list_name == "Valley AI"
            assert title == "Valley AI Reminder"
            assert body == "Open VEHR to view details."
            assert due_datetime.startswith("2026-02-16T")
            assert time_zone
            return "task-123"

        def fake_create_event(*args, **kwargs):  # noqa: ANN001
            raise AssertionError("Outlook should not be called for date-only reminders")

        monkeypatch.setattr(microsoft_graph, "create_todo_task_draft", fake_create_task)
        monkeypatch.setattr(microsoft_graph, "create_outlook_event_draft", fake_create_event)

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/ai/reminders",
                headers=_auth_header(token),
                json={
                    "title": "Something due that day",
                    "due_at": "2026-02-16T00:00:00Z",
                },
            )
            assert response.status_code == 201
            body = response.json()
            assert body["channels"]["in_chat"] is True
            assert body["channels"]["todo"] is True
            assert body.get("channels", {}).get("outlook") in {None, False}
            assert body["msft_task_id"] == "task-123"
            assert body["warnings"] == []
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_retry_is_idempotent_when_task_id_present(tmp_path, monkeypatch) -> None:
    engine, session_factory = _build_session(tmp_path)
    try:
        _token, org_id, user_id = _seed_admin_token(session_factory)

        def fake_create_task(*args, **kwargs):  # noqa: ANN001
            raise AssertionError("Graph should not be called when msft_task_id already exists")

        monkeypatch.setattr(microsoft_graph, "create_todo_task_draft", fake_create_task)

        now = utc_now()
        with session_factory() as db:
            reminder = AssistantReminder(
                organization_id=org_id,
                user_id=user_id,
                thread_id=None,
                title="Test",
                body=None,
                due_at=now + timedelta(days=1),
                channels={"in_chat": True, "todo": True},
                status="scheduled",
                repeat_mode="one_shot",
                nag_interval_minutes=None,
                msft_task_id="existing-task",
                msft_event_id=None,
                msft_next_attempt_at=now - timedelta(minutes=1),
                msft_attempt_count=0,
                msft_channel_status_json={},
            )
            db.add(reminder)
            db.commit()

            tool_db = session_factory()
            try:
                processed = retry_pending_msft_channels(db, tool_db=tool_db)
                assert processed == 1
            finally:
                tool_db.close()

            db.refresh(reminder)
            assert reminder.msft_task_id == "existing-task"
            assert reminder.msft_next_attempt_at is None
            assert reminder.msft_attempt_count == 0
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_failure_sets_backoff_and_retry_succeeds_and_audits(tmp_path, monkeypatch) -> None:
    engine, session_factory = _build_session(tmp_path)
    try:
        _token, org_id, user_id = _seed_admin_token(session_factory)

        now = utc_now()
        with session_factory() as db:
            reminder = AssistantReminder(
                organization_id=org_id,
                user_id=user_id,
                thread_id=None,
                title="Test",
                body=None,
                due_at=now + timedelta(days=1),
                channels={"in_chat": True, "todo": True},
                status="scheduled",
                repeat_mode="one_shot",
                nag_interval_minutes=None,
                msft_task_id=None,
                msft_event_id=None,
                msft_next_attempt_at=now - timedelta(minutes=1),
                msft_attempt_count=0,
                msft_channel_status_json={},
            )
            db.add(reminder)
            db.commit()

            def fail_create_task(*args, **kwargs):  # noqa: ANN001
                raise microsoft_graph.MicrosoftGraphServiceError("graph_down", status_code=503)

            monkeypatch.setattr(microsoft_graph, "create_todo_task_draft", fail_create_task)

            tool_db = session_factory()
            try:
                processed = retry_pending_msft_channels(db, tool_db=tool_db)
                assert processed == 1
            finally:
                tool_db.close()

            db.refresh(reminder)
            assert reminder.msft_task_id is None
            assert reminder.msft_attempt_count == 1
            assert reminder.msft_channel_status_json.get("todo") == "failed"
            assert reminder.msft_last_error and "graph_down" in reminder.msft_last_error
            assert reminder.msft_next_attempt_at is not None

            # Force next attempt to be due immediately.
            reminder.msft_next_attempt_at = utc_now() - timedelta(minutes=1)
            db.add(reminder)
            db.commit()

            def ok_create_task(*args, **kwargs):  # noqa: ANN001
                return "task-1"

            monkeypatch.setattr(microsoft_graph, "create_todo_task_draft", ok_create_task)

            tool_db = session_factory()
            try:
                processed = retry_pending_msft_channels(db, tool_db=tool_db)
                assert processed == 1
            finally:
                tool_db.close()

            db.refresh(reminder)
            assert reminder.msft_task_id == "task-1"
            assert reminder.msft_channel_status_json.get("todo") == "ok"
            assert reminder.msft_next_attempt_at is None
            assert reminder.msft_last_error is None

            actions = {
                row.action
                for row in db.execute(select(AuditEvent).where(AuditEvent.entity_id == reminder.id)).scalars().all()
            }
            assert "assistant_msft_channel_attempt" in actions
            assert "assistant_msft_channel_failed" in actions
            assert "assistant_msft_channel_success" in actions
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


def test_create_reminder_succeeds_even_when_graph_fails(tmp_path, monkeypatch) -> None:
    engine, session_factory = _build_session(tmp_path)
    try:
        token, _org_id, _user_id = _seed_admin_token(session_factory)

        def fail_create_event(*args, **kwargs):  # noqa: ANN001
            raise microsoft_graph.MicrosoftGraphServiceError("outlook_down", status_code=503)

        monkeypatch.setattr(microsoft_graph, "create_outlook_event_draft", fail_create_event)

        with TestClient(app) as client:
            response = client.post(
                "/api/v1/ai/reminders",
                headers=_auth_header(token),
                json={
                    "title": "Follow up",
                    "due_at": "2026-02-16T15:00:00Z",
                },
            )
            assert response.status_code == 201
            body = response.json()
            assert body["channels"]["outlook"] is True
            assert body["msft_event_id"] is None
            assert "msft_outlook_create_failed" in body["warnings"]
            assert body["msft_next_attempt_at"] is not None
            assert body["msft_attempt_count"] == 1
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()
