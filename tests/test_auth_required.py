from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.rbac import ROLE_ADMIN
from app.core.security import create_access_token, hash_password
from app.db.base import Base
from app.db.models.organization import Organization
from app.db.models.organization_membership import OrganizationMembership
from app.db.models.user import User
from app.db.session import get_db
from app.main import app


def _setup_sqlite(tmp_path: Path):
    engine = create_engine(f"sqlite:///{tmp_path/'auth_required.sqlite'}", connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    from app.db import models as _models  # noqa: F401

    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    return TestingSessionLocal


def _seed_admin(db_session) -> str:
    with db_session() as db:
        org = Organization(name="Auth Org")
        db.add(org)
        db.flush()
        user = User(
            email="auth-admin@example.com",
            full_name="Auth Admin",
            hashed_password=hash_password("Password123!"),
            is_active=True,
        )
        db.add(user)
        db.flush()
        db.add(OrganizationMembership(organization_id=org.id, user_id=user.id, role=ROLE_ADMIN))
        db.commit()
        return create_access_token({"sub": user.id, "org_id": org.id})


def test_revenue_upload_requires_auth_and_accepts_valid_token(tmp_path, monkeypatch, auth_headers) -> None:
    session_factory = _setup_sqlite(tmp_path)
    token = _seed_admin(session_factory)
    try:
        with TestClient(app) as client:
            unauth = client.post(
                "/api/v1/revenue/era-pdfs/upload",
                files=[("files", ("era.pdf", b"%PDF-1.4 auth", "application/pdf"))],
            )
            assert unauth.status_code == 401

            authed = client.post(
                "/api/v1/revenue/era-pdfs/upload",
                files=[("files", ("era-auth.pdf", b"%PDF-1.4 auth", "application/pdf"))],
                headers=auth_headers(token),
            )
            assert authed.status_code != 401
    finally:
        app.dependency_overrides.clear()
