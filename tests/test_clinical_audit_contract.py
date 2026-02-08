from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.rbac import ROLE_CLINICIAN, ROLE_COMPLIANCE
from app.core.security import create_access_token
from app.db.base import Base
from app.db.models.form_submission import FormSubmission
from app.db.models.form_template import FormTemplate
from app.db.models.organization import Organization
from app.db.models.organization_membership import OrganizationMembership
from app.db.models.patient import Patient
from app.db.models.user import User
from app.db.session import get_db
from app.main import app
from app.core.time import utc_now


DUMMY_HASH = "test-hash-not-used-in-this-suite"


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create_org_user_membership(db, *, org_name: str, email: str, role: str) -> tuple[Organization, User]:
    org = Organization(name=org_name)
    db.add(org)
    db.flush()

    user = User(
        email=email,
        full_name=email.split("@", 1)[0],
        hashed_password=DUMMY_HASH,
        is_active=True,
    )
    db.add(user)
    db.flush()

    membership = OrganizationMembership(
        organization_id=org.id,
        user_id=user.id,
        role=role,
    )
    db.add(membership)
    db.commit()
    db.refresh(org)
    db.refresh(user)
    return org, user


def _create_user_for_org(db, *, organization_id: str, email: str, role: str) -> User:
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
    database_file = tmp_path / "clinical_audit_contract.sqlite"
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


def _seed_assessment_submission(db, *, organization_id: str) -> tuple[str, str]:
    patient = Patient(
        organization_id=organization_id,
        first_name="Alex",
        last_name="Audit",
        dob=None,
        phone=None,
        email=None,
    )
    db.add(patient)
    db.flush()

    template = FormTemplate(
        organization_id=organization_id,
        name="Initial Assessment",
        version=1,
        status="published",
        schema_json=json.dumps(
            {
                "type": "object",
                "required": ["dimensions"],
                "properties": {"dimensions": {"type": "array"}},
            }
        ),
    )
    db.add(template)
    db.flush()

    assessment_payload = {
        "dimensions": [
            {"key": "depression", "score": "High", "score_required": True},
            {"key": "anxiety", "score_required": True},
        ]
    }
    submission = FormSubmission(
        organization_id=organization_id,
        patient_id=patient.id,
        encounter_id=None,
        form_template_id=template.id,
        submitted_data_json=json.dumps(assessment_payload),
        pdf_uri=None,
        created_at=utc_now(),
    )
    db.add(submission)
    db.commit()
    return submission.id, patient.id


def test_clinical_audit_tenant_isolation(client: TestClient, session_factory) -> None:
    with session_factory() as db:
        org_a, reviewer_a = _create_org_user_membership(
            db,
            org_name="OrgA",
            email="orga-reviewer@example.com",
            role=ROLE_COMPLIANCE,
        )
        runner_a = _create_user_for_org(
            db,
            organization_id=org_a.id,
            email="orga-runner@example.com",
            role=ROLE_CLINICIAN,
        )
        org_b, reviewer_b = _create_org_user_membership(
            db,
            org_name="OrgB",
            email="orgb-reviewer@example.com",
            role=ROLE_COMPLIANCE,
        )

        submission_id, _ = _seed_assessment_submission(db, organization_id=org_a.id)
        runner_token = create_access_token({"sub": runner_a.id, "org_id": org_a.id})
        reviewer_a_token = create_access_token({"sub": reviewer_a.id, "org_id": org_a.id})
        reviewer_b_token = create_access_token({"sub": reviewer_b.id, "org_id": org_b.id})

    run_response = client.post(
        "/api/v1/clinical-audit/run",
        json={"subject_type": "assessment", "subject_id": submission_id, "mode": "deterministic_only"},
        headers=_auth_header(runner_token),
    )
    assert run_response.status_code == 200
    run_id = run_response.json()["run_id"]

    org_a_findings = client.get("/api/v1/clinical-audit/findings", headers=_auth_header(reviewer_a_token))
    assert org_a_findings.status_code == 200
    assert len(org_a_findings.json()) >= 1

    org_b_runs = client.get("/api/v1/clinical-audit/runs", headers=_auth_header(reviewer_b_token))
    assert org_b_runs.status_code == 200
    assert org_b_runs.json() == []

    org_b_findings = client.get("/api/v1/clinical-audit/findings", headers=_auth_header(reviewer_b_token))
    assert org_b_findings.status_code == 200
    assert org_b_findings.json() == []

    org_b_run_detail = client.get(f"/api/v1/clinical-audit/runs/{run_id}", headers=_auth_header(reviewer_b_token))
    assert org_b_run_detail.status_code == 404


def test_findings_endpoint_blocks_non_reviewer_role(client: TestClient, session_factory) -> None:
    with session_factory() as db:
        org, runner = _create_org_user_membership(
            db,
            org_name="RBACOrg",
            email="runner@example.com",
            role=ROLE_CLINICIAN,
        )
        submission_id, _ = _seed_assessment_submission(db, organization_id=org.id)
        runner_token = create_access_token({"sub": runner.id, "org_id": org.id})

    run_response = client.post(
        "/api/v1/clinical-audit/run",
        json={"subject_type": "assessment", "subject_id": submission_id, "mode": "deterministic_only"},
        headers=_auth_header(runner_token),
    )
    assert run_response.status_code == 200

    findings_response = client.get("/api/v1/clinical-audit/findings", headers=_auth_header(runner_token))
    assert findings_response.status_code == 403


def test_deterministic_findings_and_audit_events(client: TestClient, session_factory) -> None:
    with session_factory() as db:
        org, reviewer = _create_org_user_membership(
            db,
            org_name="DeterministicOrg",
            email="reviewer@example.com",
            role=ROLE_COMPLIANCE,
        )
        runner = _create_user_for_org(
            db,
            organization_id=org.id,
            email="det-runner@example.com",
            role=ROLE_CLINICIAN,
        )

        submission_id, _ = _seed_assessment_submission(db, organization_id=org.id)
        runner_token = create_access_token({"sub": runner.id, "org_id": org.id})
        reviewer_token = create_access_token({"sub": reviewer.id, "org_id": org.id})

    run_response = client.post(
        "/api/v1/clinical-audit/run",
        json={"subject_type": "assessment", "subject_id": submission_id, "mode": "deterministic_only"},
        headers=_auth_header(runner_token),
    )
    assert run_response.status_code == 200
    run_payload = run_response.json()
    assert run_payload["finding_count"] >= 2
    assert run_payload["high_severity_count"] >= 1
    run_id = run_payload["run_id"]

    findings_response = client.get(
        f"/api/v1/clinical-audit/findings?run_id={run_id}",
        headers=_auth_header(reviewer_token),
    )
    assert findings_response.status_code == 200
    findings = findings_response.json()
    assert any(
        finding["signal_type"] == "plan_alignment" and finding["severity"] == "high"
        for finding in findings
    )

    warning_finding = next((finding for finding in findings if finding["severity"] == "warning"), None)
    assert warning_finding is not None
    queue_response = client.post(
        f"/api/v1/clinical-audit/findings/{warning_finding['id']}/queue",
        headers=_auth_header(reviewer_token),
    )
    assert queue_response.status_code == 200
    queue_id = queue_response.json()["id"]

    audit_run_events = client.get(
        "/api/v1/audit/events?entity_type=clinical_audit_run",
        headers=_auth_header(reviewer_token),
    )
    assert audit_run_events.status_code == 200
    run_events = [
        event
        for event in audit_run_events.json()
        if event["entity_id"] == run_id and event["action"] in {"clinical_audit.run_started", "clinical_audit.run_completed"}
    ]
    assert {event["action"] for event in run_events} == {
        "clinical_audit.run_started",
        "clinical_audit.run_completed",
    }

    audit_queue_events = client.get(
        "/api/v1/audit/events?entity_type=review_queue_item",
        headers=_auth_header(reviewer_token),
    )
    assert audit_queue_events.status_code == 200
    assert any(
        event["entity_id"] == queue_id and event["action"] == "review_queue_item.created_from_finding"
        for event in audit_queue_events.json()
    )



