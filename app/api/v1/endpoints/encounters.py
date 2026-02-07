from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_membership, get_current_organization, require_permission
from app.db.models.encounter import Encounter
from app.db.models.patient import Patient
from app.db.session import get_db
from app.services.audit import log_event


router = APIRouter(tags=["Encounters"])


class EncounterCreate(BaseModel):
    patient_id: str
    encounter_type: str
    start_time: datetime
    end_time: datetime | None = None
    clinician: str | None = None
    location: str | None = None
    modality: str | None = None


class EncounterRead(BaseModel):
    id: str
    patient_id: str
    encounter_type: str
    start_time: datetime
    end_time: datetime | None = None
    clinician: str | None = None
    location: str | None = None
    modality: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class PatientEncounterCreate(BaseModel):
    encounter_type: str
    start_time: datetime
    end_time: datetime | None = None
    clinician: str | None = None
    location: str | None = None
    modality: str | None = None


@router.post("/encounters", response_model=EncounterRead, status_code=status.HTTP_201_CREATED)
def create_encounter(
    payload: EncounterCreate,
    db: Session = Depends(get_db),
    organization=Depends(get_current_organization),
    membership=Depends(get_current_membership),
    _: None = Depends(require_permission("encounters:write")),
) -> EncounterRead:
    patient = db.execute(
        select(Patient).where(
            Patient.id == payload.patient_id,
            Patient.organization_id == organization.id,
        )
    ).scalar_one_or_none()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    encounter = Encounter(
        organization_id=organization.id,
        patient_id=payload.patient_id,
        encounter_type=payload.encounter_type,
        start_time=payload.start_time,
        end_time=payload.end_time,
        clinician=payload.clinician,
        location=payload.location,
        modality=payload.modality,
    )
    db.add(encounter)
    db.commit()
    db.refresh(encounter)
    log_event(
        db,
        action="create_encounter",
        entity_type="encounter",
        entity_id=encounter.id,
        organization_id=organization.id,
        patient_id=encounter.patient_id,
        actor=membership.user.email,
    )
    return encounter


@router.post(
    "/patients/{patient_id}/encounters",
    response_model=EncounterRead,
    status_code=status.HTTP_201_CREATED,
)
def create_encounter_for_patient(
    patient_id: str,
    payload: PatientEncounterCreate,
    db: Session = Depends(get_db),
    organization=Depends(get_current_organization),
    membership=Depends(get_current_membership),
    _: None = Depends(require_permission("encounters:write")),
) -> EncounterRead:
    patient = db.execute(
        select(Patient).where(
            Patient.id == patient_id,
            Patient.organization_id == organization.id,
        )
    ).scalar_one_or_none()
    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Patient not found",
        )

    encounter = Encounter(
        organization_id=organization.id,
        patient_id=patient_id,
        encounter_type=payload.encounter_type,
        start_time=payload.start_time,
        end_time=payload.end_time,
        clinician=payload.clinician,
        location=payload.location,
        modality=payload.modality,
    )
    db.add(encounter)
    db.commit()
    db.refresh(encounter)
    log_event(
        db,
        action="create_encounter",
        entity_type="encounter",
        entity_id=encounter.id,
        organization_id=organization.id,
        patient_id=encounter.patient_id,
        actor=membership.user.email,
    )
    return encounter


@router.get("/encounters/{encounter_id}", response_model=EncounterRead)
def get_encounter(
    encounter_id: str,
    db: Session = Depends(get_db),
    organization=Depends(get_current_organization),
    membership=Depends(get_current_membership),
    _: None = Depends(require_permission("encounters:read")),
) -> EncounterRead:
    encounter = db.execute(
        select(Encounter).where(
            Encounter.id == encounter_id,
            Encounter.organization_id == organization.id,
        )
    ).scalar_one_or_none()
    if not encounter:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Encounter not found",
        )
    log_event(
        db,
        action="view_encounter",
        entity_type="encounter",
        entity_id=encounter.id,
        organization_id=organization.id,
        patient_id=encounter.patient_id,
        actor=membership.user.email,
    )
    return encounter


@router.get("/patients/{patient_id}/encounters", response_model=list[EncounterRead])
def list_encounters_by_patient(
    patient_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    organization=Depends(get_current_organization),
    _: None = Depends(require_permission("encounters:read")),
) -> list[EncounterRead]:
    encounters = (
        db.execute(
            select(Encounter)
            .where(Encounter.patient_id == patient_id)
            .where(Encounter.organization_id == organization.id)
            .offset(offset)
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return encounters
