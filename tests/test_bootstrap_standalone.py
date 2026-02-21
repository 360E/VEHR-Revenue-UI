from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.db.models.organization import Organization
from app.db.models.organization_membership import OrganizationMembership
from app.db.models.user import User
from app.db.session import get_db
from app.main import app


def _setup_sqlite(tmp_path):
    engine = create_engine(
        f"sqlite:///{tmp_path/'bootstrap.sqlite'}",
        connect_args={"check_same_thread": False},
    )
    testing_session = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    from app.db import models as _models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = testing_session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return testing_session


def test_bootstrap_gate_disabled_returns_404(tmp_path, monkeypatch) -> None:
    _setup_sqlite(tmp_path)
    monkeypatch.setenv("BOOTSTRAP_ENABLED", "0")
    payload = {
        "organization_name": "Standalone Org",
        "admin_email": "admin@standalone.example",
        "admin_password": "Password123!",
    }

    try:
        with TestClient(app) as client:
            response = client.post("/api/v1/bootstrap", json=payload)
            assert response.status_code == 404
    finally:
        app.dependency_overrides.clear()


def test_bootstrap_is_idempotent_and_allows_login(tmp_path, monkeypatch) -> None:
    session_factory = _setup_sqlite(tmp_path)
    monkeypatch.setenv("BOOTSTRAP_ENABLED", "1")
    payload = {
        "organization_name": "Standalone Org",
        "admin_email": "admin@standalone.example",
        "admin_password": "Password123!",
        "admin_name": "Standalone Admin",
    }

    try:
        with TestClient(app) as client:
            first = client.post("/api/v1/bootstrap", json=payload)
            second = client.post("/api/v1/bootstrap", json=payload)
            assert first.status_code == 201
            assert second.status_code == 201
            assert first.json() == second.json()

            login = client.post(
                "/api/v1/auth/login",
                json={"email": payload["admin_email"], "password": payload["admin_password"]},
            )
            assert login.status_code == 200
            assert login.json()["organization_id"] == first.json()["organization_id"]

        with session_factory() as db:
            organizations = db.execute(select(Organization)).scalars().all()
            users = db.execute(select(User)).scalars().all()
            memberships = db.execute(select(OrganizationMembership)).scalars().all()
            assert len(organizations) == 1
            assert len(users) == 1
            assert len(memberships) == 1
    finally:
        app.dependency_overrides.clear()
