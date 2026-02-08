from __future__ import annotations

import json
import os

from sqlalchemy import select

from app.core.rbac import ROLE_CLINICIAN, ROLE_COMPLIANCE
from app.core.security import hash_password
from app.db.models.encounter import Encounter
from app.db.models.form_template import FormTemplate
from app.db.models.organization import Organization
from app.db.models.organization_membership import OrganizationMembership
from app.db.models.patient import Patient
from app.db.models.user import User
from app.db.session import SessionLocal
from app.core.time import utc_now


DEFAULT_ASSESSMENT_SCHEMA = {
    "title": "Initial Assessment",
    "type": "object",
    "fields": [
        {"id": "dimension_depression", "label": "Depression Severity", "type": "select", "required": True, "options": ["Low", "Moderate", "High"]},
        {"id": "dimension_anxiety", "label": "Anxiety Severity", "type": "select", "required": True, "options": ["Low", "Moderate", "High"]},
        {"id": "plan_summary", "label": "Treatment Plan Summary", "type": "textarea", "required": False},
    ],
}


def _env(name: str, default: str) -> str:
    return os.getenv(name, default).strip()


def _ensure_org(db, name: str) -> Organization:
    org = db.execute(select(Organization).where(Organization.name == name)).scalar_one_or_none()
    if org:
        return org
    org = Organization(name=name)
    db.add(org)
    db.commit()
    db.refresh(org)
    return org


def _ensure_user_with_membership(db, *, organization_id: str, email: str, role: str, password: str, full_name: str | None) -> User:
    email_normalized = email.lower().strip()
    user = db.execute(select(User).where(User.email == email_normalized)).scalar_one_or_none()
    if not user:
        user = User(
            email=email_normalized,
            full_name=full_name,
            hashed_password=hash_password(password),
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    membership = db.execute(
        select(OrganizationMembership).where(
            OrganizationMembership.organization_id == organization_id,
            OrganizationMembership.user_id == user.id,
        )
    ).scalar_one_or_none()
    if not membership:
        membership = OrganizationMembership(
            organization_id=organization_id,
            user_id=user.id,
            role=role,
        )
        db.add(membership)
        db.commit()

    return user


def _ensure_patient(db, organization_id: str) -> Patient:
    patient = db.execute(
        select(Patient).where(
            Patient.organization_id == organization_id,
            Patient.first_name == "Demo",
            Patient.last_name == "Patient",
        )
    ).scalar_one_or_none()
    if patient:
        return patient

    patient = Patient(
        organization_id=organization_id,
        first_name="Demo",
        last_name="Patient",
        dob=None,
        phone="555-000-0000",
        email="demo.patient@example.com",
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)
    return patient


def _ensure_encounter(db, organization_id: str, patient_id: str) -> Encounter:
    encounter = db.execute(
        select(Encounter).where(
            Encounter.organization_id == organization_id,
            Encounter.patient_id == patient_id,
            Encounter.encounter_type == "initial-intake",
        )
    ).scalar_one_or_none()
    if encounter:
        return encounter

    encounter = Encounter(
        organization_id=organization_id,
        patient_id=patient_id,
        encounter_type="initial-intake",
        start_time=utc_now(),
        end_time=None,
        clinician="Demo Clinician",
        location="Main Clinic",
        modality="in-person",
    )
    db.add(encounter)
    db.commit()
    db.refresh(encounter)
    return encounter


def _ensure_published_assessment_template(db, organization_id: str) -> FormTemplate:
    existing = db.execute(
        select(FormTemplate).where(
            FormTemplate.organization_id == organization_id,
            FormTemplate.name == "Initial Assessment",
            FormTemplate.status == "published",
        )
    ).scalar_one_or_none()
    if existing:
        return existing

    max_version = db.execute(
        select(FormTemplate.version)
        .where(
            FormTemplate.organization_id == organization_id,
            FormTemplate.name == "Initial Assessment",
        )
        .order_by(FormTemplate.version.desc())
        .limit(1)
    ).scalar_one_or_none()
    next_version = (max_version or 0) + 1

    template = FormTemplate(
        organization_id=organization_id,
        name="Initial Assessment",
        description="Seeded clinical assessment template",
        version=next_version,
        status="published",
        schema_json=json.dumps(DEFAULT_ASSESSMENT_SCHEMA),
    )
    db.add(template)
    db.commit()
    db.refresh(template)
    return template


def main() -> None:
    org_name = _env("VEHR_SEED_ORG_NAME", "VEHR Demo Org")
    clinician_email = _env("VEHR_SEED_CLINICIAN_EMAIL", "clinician.demo@vehr.local")
    reviewer_email = _env("VEHR_SEED_REVIEWER_EMAIL", "reviewer.demo@vehr.local")
    seed_password = _env("VEHR_SEED_PASSWORD", "ChangeMe123!")

    db = SessionLocal()
    try:
        org = _ensure_org(db, org_name)
        clinician = _ensure_user_with_membership(
            db,
            organization_id=org.id,
            email=clinician_email,
            role=ROLE_CLINICIAN,
            password=seed_password,
            full_name="Demo Clinician",
        )
        reviewer = _ensure_user_with_membership(
            db,
            organization_id=org.id,
            email=reviewer_email,
            role=ROLE_COMPLIANCE,
            password=seed_password,
            full_name="Demo Reviewer",
        )
        patient = _ensure_patient(db, org.id)
        encounter = _ensure_encounter(db, org.id, patient.id)
        template = _ensure_published_assessment_template(db, org.id)

        print("seed_demo complete")
        print(f"organization_id={org.id}")
        print(f"clinician_user_id={clinician.id}")
        print(f"reviewer_user_id={reviewer.id}")
        print(f"patient_id={patient.id}")
        print(f"encounter_id={encounter.id}")
        print(f"assessment_template_id={template.id}")
    finally:
        db.close()


if __name__ == "__main__":
    main()




