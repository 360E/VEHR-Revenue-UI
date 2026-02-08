from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.rbac import ROLE_ADMIN, ROLE_STAFF
from app.core.security import create_access_token
from app.db.base import Base
from app.db.models.form_template import FormTemplate
from app.db.models.organization import Organization
from app.db.models.organization_membership import OrganizationMembership
from app.db.models.user import User
from app.db.session import get_db
from app.main import app


DUMMY_HASH = "test-hash-not-used-in-this-suite"


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_user_with_membership(db, *, organization_id: str, email: str, role: str) -> User:
    user = User(
        email=email,
        full_name=email.split("@", 1)[0],
        hashed_password=DUMMY_HASH,
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.add(
        OrganizationMembership(
            organization_id=organization_id,
            user_id=user.id,
            role=role,
        )
    )
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture()
def session_factory(tmp_path):
    database_file = tmp_path / "forms_generation.sqlite"
    engine = create_engine(
        f"sqlite:///{database_file}",
        connect_args={"check_same_thread": False},
    )
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
    try:
        yield TestingSessionLocal
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()


@pytest.fixture()
def client(session_factory):
    with TestClient(app) as test_client:
        yield test_client


def test_form_generation_requires_manage_permission(client: TestClient, session_factory) -> None:
    with session_factory() as db:
        org = Organization(name="FormsRBAC")
        db.add(org)
        db.flush()

        admin_user = _create_user_with_membership(
            db,
            organization_id=org.id,
            email="forms-admin@example.com",
            role=ROLE_ADMIN,
        )
        staff_user = _create_user_with_membership(
            db,
            organization_id=org.id,
            email="forms-staff@example.com",
            role=ROLE_STAFF,
        )

        template = FormTemplate(
            organization_id=org.id,
            name="Progress Note",
            version=1,
            status="draft",
            schema_json=json.dumps(
                {"type": "object", "fields": [{"id": "note", "label": "Note", "type": "textarea"}]}
            ),
        )
        db.add(template)
        db.commit()
        template_id = template.id
        org_id = org.id
        admin_user_id = admin_user.id
        staff_user_id = staff_user.id

    denied = client.post(
        f"/api/v1/forms/templates/{template_id}/generate",
        json={"prompt": "Build an intake assessment form"},
        headers=_auth_header(create_access_token({"sub": staff_user_id, "org_id": org_id})),
    )
    assert denied.status_code == 403

    allowed = client.post(
        f"/api/v1/forms/templates/{template_id}/generate",
        json={"prompt": "Build an intake assessment form"},
        headers=_auth_header(create_access_token({"sub": admin_user_id, "org_id": org_id})),
    )
    assert allowed.status_code == 200
    assert "template" in allowed.json()


def test_published_templates_are_immutable(client: TestClient, session_factory) -> None:
    with session_factory() as db:
        org = Organization(name="FormsImmutability")
        db.add(org)
        db.flush()

        admin_user = _create_user_with_membership(
            db,
            organization_id=org.id,
            email="immut-admin@example.com",
            role=ROLE_ADMIN,
        )

        template = FormTemplate(
            organization_id=org.id,
            name="Initial Assessment",
            version=1,
            status="published",
            schema_json=json.dumps(
                {"type": "object", "fields": [{"id": "risk", "label": "Risk", "type": "select", "options": ["Low", "High"]}]}
            ),
        )
        db.add(template)
        db.commit()
        template_id = template.id

        token = create_access_token({"sub": admin_user.id, "org_id": org.id})

    response = client.patch(
        f"/api/v1/forms/templates/{template_id}",
        json={
            "name": "Updated Name Should Fail",
            "schema": {"type": "object", "fields": [{"id": "risk", "label": "Risk", "type": "text"}]},
        },
        headers=_auth_header(token),
    )
    assert response.status_code == 409


def test_generation_rejects_invalid_schema_from_provider(client: TestClient, session_factory, monkeypatch) -> None:
    with session_factory() as db:
        org = Organization(name="FormsValidation")
        db.add(org)
        db.flush()
        admin_user = _create_user_with_membership(
            db,
            organization_id=org.id,
            email="validator-admin@example.com",
            role=ROLE_ADMIN,
        )
        template = FormTemplate(
            organization_id=org.id,
            name="Validator Test",
            version=1,
            status="draft",
            schema_json=json.dumps(
                {"type": "object", "fields": [{"id": "text", "label": "Text", "type": "text"}]}
            ),
        )
        db.add(template)
        db.commit()
        template_id = template.id
        token = create_access_token({"sub": admin_user.id, "org_id": org.id})

    from app.api.v1.endpoints import forms as forms_endpoint

    def _bad_schema(_prompt: str):
        return {"fields": [{"id": "bad", "label": "Bad", "type": "unsupported"}]}

    monkeypatch.setattr(forms_endpoint, "generate_schema_from_prompt", _bad_schema)

    response = client.post(
        f"/api/v1/forms/templates/{template_id}/generate",
        json={"prompt": "generate broken schema"},
        headers=_auth_header(token),
    )
    assert response.status_code == 400
    assert "unsupported type" in response.json()["detail"].lower()


def test_form_generation_is_tenant_scoped(client: TestClient, session_factory) -> None:
    with session_factory() as db:
        org_a = Organization(name="OrgA Forms")
        org_b = Organization(name="OrgB Forms")
        db.add(org_a)
        db.add(org_b)
        db.flush()

        admin_a = _create_user_with_membership(
            db,
            organization_id=org_a.id,
            email="orga-admin@example.com",
            role=ROLE_ADMIN,
        )
        admin_b = _create_user_with_membership(
            db,
            organization_id=org_b.id,
            email="orgb-admin@example.com",
            role=ROLE_ADMIN,
        )

        template_a = FormTemplate(
            organization_id=org_a.id,
            name="OrgA Template",
            version=1,
            status="draft",
            schema_json=json.dumps(
                {"type": "object", "fields": [{"id": "a", "label": "A", "type": "text"}]}
            ),
        )
        db.add(template_a)
        db.commit()
        template_a_id = template_a.id

        org_b_token = create_access_token({"sub": admin_b.id, "org_id": org_b.id})

    response = client.post(
        f"/api/v1/forms/templates/{template_a_id}/generate",
        json={"prompt": "Generate schema"},
        headers=_auth_header(org_b_token),
    )
    assert response.status_code == 404
