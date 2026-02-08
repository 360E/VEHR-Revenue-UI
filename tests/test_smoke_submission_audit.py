from __future__ import annotations

import json

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.core.rbac import ROLE_CLINICIAN
from app.core.security import create_access_token
from app.db.base import Base
from app.db.models.clinical_audit_run import ClinicalAuditRun
from app.db.models.form_template import FormTemplate
from app.db.models.organization import Organization
from app.db.models.organization_membership import OrganizationMembership
from app.db.models.user import User
from app.db.session import get_db
from app.main import app
from app.core.time import utc_now


DUMMY_HASH = "test-hash-not-used-in-this-suite"


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_smoke_patient_encounter_submission_triggers_audit(tmp_path) -> None:
    database_file = tmp_path / "smoke_submission.sqlite"
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
        with TestingSessionLocal() as db:
            org = Organization(name="SmokeOrg")
            db.add(org)
            db.flush()

            user = User(
                email="smoke-clinician@example.com",
                full_name="Smoke Clinician",
                hashed_password=DUMMY_HASH,
                is_active=True,
            )
            db.add(user)
            db.flush()
            db.add(
                OrganizationMembership(
                    organization_id=org.id,
                    user_id=user.id,
                    role=ROLE_CLINICIAN,
                )
            )

            template = FormTemplate(
                organization_id=org.id,
                name="Initial Assessment",
                version=1,
                status="published",
                schema_json=json.dumps(
                    {
                        "type": "object",
                        "fields": [
                            {
                                "id": "dimension_depression",
                                "label": "Depression Severity",
                                "type": "select",
                                "required": True,
                                "options": ["Low", "Moderate", "High"],
                            }
                        ],
                    }
                ),
            )
            db.add(template)
            db.commit()

            org_id = org.id
            user_id = user.id
            template_id = template.id

        token = create_access_token({"sub": user_id, "org_id": org_id})

        with TestClient(app) as client:
            create_patient = client.post(
                "/api/v1/patients",
                json={"first_name": "Smoke", "last_name": "Patient"},
                headers=_auth_header(token),
            )
            assert create_patient.status_code == 201
            patient_id = create_patient.json()["id"]

            create_encounter = client.post(
                f"/api/v1/patients/{patient_id}/encounters",
                json={
                    "encounter_type": "intake",
                    "start_time": utc_now().isoformat(),
                },
                headers=_auth_header(token),
            )
            assert create_encounter.status_code == 201
            encounter_id = create_encounter.json()["id"]

            submit = client.post(
                "/api/v1/forms/submit",
                json={
                    "patient_id": patient_id,
                    "template_version_id": template_id,
                    "encounter_id": encounter_id,
                    "submitted_data": {"dimension_depression": "High"},
                },
                headers=_auth_header(token),
            )
            assert submit.status_code == 201
            submission_id = submit.json()["id"]

        with TestingSessionLocal() as db:
            run = db.execute(
                select(ClinicalAuditRun).where(
                    ClinicalAuditRun.organization_id == org_id,
                    ClinicalAuditRun.subject_type == "assessment",
                    ClinicalAuditRun.subject_id == submission_id,
                )
            ).scalar_one_or_none()
            assert run is not None
    finally:
        app.dependency_overrides.clear()
        Base.metadata.drop_all(bind=engine)
        engine.dispose()




