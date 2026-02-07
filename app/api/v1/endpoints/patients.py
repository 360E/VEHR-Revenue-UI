from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_membership, get_current_organization, require_permission
from app.db.models.patient import Patient
from app.db.session import get_db
from app.services.audit import log_event


router = APIRouter(tags=["Patients"])


class PatientCreate(BaseModel):
    first_name: str
    last_name: str
    dob: date | None = None
    phone: str | None = None
    email: str | None = None


class PatientRead(BaseModel):
    id: str
    first_name: str
    last_name: str
    dob: date | None = None
    phone: str | None = None
    email: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


@router.post("/patients", response_model=PatientRead, status_code=status.HTTP_201_CREATED)
def create_patient(
    payload: PatientCreate,
    db: Session = Depends(get_db),
    organization=Depends(get_current_organization),
    membership=Depends(get_current_membership),
    _: None = Depends(require_permission("patients:write")),
) -> PatientRead:
    patient = Patient(
        organization_id=organization.id,
        first_name=payload.first_name,
        last_name=payload.last_name,
        dob=payload.dob,
        phone=payload.phone,
        email=payload.email,
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)

    log_event(
        db,
        action="create_patient",
        entity_type="patient",
        entity_id=patient.id,
        organization_id=organization.id,
        patient_id=patient.id,
        actor=membership.user.email,
    )
    return patient


@router.get("/patients", response_model=list[PatientRead])
def list_patients(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    organization=Depends(get_current_organization),
    _: None = Depends(require_permission("patients:read")),
) -> list[PatientRead]:
    patients = (
        db.execute(
            select(Patient)
            .where(Patient.organization_id == organization.id)
            .offset(offset)
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return patients


@router.get("/patients/{patient_id}", response_model=PatientRead)
def get_patient(
    patient_id: str,
    db: Session = Depends(get_db),
    organization=Depends(get_current_organization),
    membership=Depends(get_current_membership),
    _: None = Depends(require_permission("patients:read")),
) -> PatientRead:
    patient = db.execute(
        select(Patient).where(
            Patient.id == patient_id,
            Patient.organization_id == organization.id,
        )
    ).scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")
    log_event(
        db,
        action="view_patient",
        entity_type="patient",
        entity_id=patient.id,
        organization_id=organization.id,
        patient_id=patient.id,
        actor=membership.user.email,
    )
    return patient
