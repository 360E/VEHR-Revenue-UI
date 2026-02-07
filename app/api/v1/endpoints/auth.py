from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.deps import get_current_membership, require_permission
from app.core.rbac import ROLE_ADMIN, is_valid_role
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models.organization import Organization
from app.db.models.organization_membership import OrganizationMembership
from app.db.models.user import User
from app.db.models.patient import Patient
from app.db.models.encounter import Encounter
from app.db.models.form_template import FormTemplate
from app.db.models.form_submission import FormSubmission
from app.db.models.audit_event import AuditEvent
from app.db.session import get_db
from app.services.audit import log_event


router = APIRouter(tags=["Auth"])


class LoginRequest(BaseModel):
    email: str
    password: str
    organization_id: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int
    organization_id: str
    user_id: str


class BootstrapRequest(BaseModel):
    organization_name: str
    admin_email: str
    admin_password: str
    admin_name: str | None = None


class UserCreate(BaseModel):
    email: str
    full_name: str | None = None
    password: str
    role: str


class UserRead(BaseModel):
    id: str
    email: str
    full_name: str | None = None
    role: str
    is_active: bool


class MeResponse(BaseModel):
    id: str
    email: str
    full_name: str | None = None
    role: str
    organization_id: str


@router.post("/auth/bootstrap", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def bootstrap(request: BootstrapRequest, db: Session = Depends(get_db)) -> TokenResponse:
    existing_users = db.execute(select(func.count(User.id))).scalar_one()
    existing_orgs = db.execute(select(func.count(Organization.id))).scalar_one()
    if existing_users > 0 or existing_orgs > 0:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bootstrap is disabled once data exists",
        )

    org = Organization(name=request.organization_name)
    db.add(org)
    db.commit()
    db.refresh(org)

    admin_email = request.admin_email.strip().lower()
    user = User(
        email=admin_email,
        full_name=request.admin_name,
        hashed_password=hash_password(request.admin_password),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    membership = OrganizationMembership(
        organization_id=org.id,
        user_id=user.id,
        role=ROLE_ADMIN,
    )
    db.add(membership)
    db.commit()

    for model in (Patient, Encounter, FormTemplate, FormSubmission, AuditEvent):
        db.execute(
            update(model)
            .where(model.organization_id.is_(None))
            .values(organization_id=org.id)
        )
    db.commit()

    log_event(
        db,
        action="bootstrap",
        entity_type="organization",
        entity_id=org.id,
        organization_id=org.id,
        actor=user.email,
    )

    token = create_access_token(
        {"sub": user.id, "org_id": org.id},
        expires_delta=timedelta(minutes=60),
    )
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=60 * 60,
        organization_id=org.id,
        user_id=user.id,
    )


@router.post("/auth/login", response_model=TokenResponse)
def login(request: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    email = request.email.strip().lower()
    user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if not user or not verify_password(request.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )
    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User is inactive",
        )

    memberships = db.execute(
        select(OrganizationMembership).where(OrganizationMembership.user_id == user.id)
    ).scalars().all()
    if not memberships:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User has no organization membership",
        )

    organization_id = request.organization_id
    if organization_id:
        membership = next(
            (m for m in memberships if m.organization_id == organization_id),
            None,
        )
        if not membership:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Organization access denied",
            )
    else:
        if len(memberships) > 1:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="organization_id required for multi-organization users",
            )
        membership = memberships[0]
        organization_id = membership.organization_id

    token = create_access_token({"sub": user.id, "org_id": organization_id})
    return TokenResponse(
        access_token=token,
        token_type="bearer",
        expires_in=60 * 60,
        organization_id=organization_id,
        user_id=user.id,
    )


@router.get("/auth/me", response_model=MeResponse)
def me(
    membership: OrganizationMembership = Depends(get_current_membership),
) -> MeResponse:
    return MeResponse(
        id=membership.user.id,
        email=membership.user.email,
        full_name=membership.user.full_name,
        role=membership.role,
        organization_id=membership.organization_id,
    )


@router.post("/users", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    request: UserCreate,
    db: Session = Depends(get_db),
    membership: OrganizationMembership = Depends(get_current_membership),
    _: None = Depends(require_permission("users:manage")),
) -> UserRead:
    if not is_valid_role(request.role):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid role",
        )

    email = request.email.strip().lower()
    existing = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Email already exists",
        )

    user = User(
        email=email,
        full_name=request.full_name,
        hashed_password=hash_password(request.password),
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    membership_record = OrganizationMembership(
        organization_id=membership.organization_id,
        user_id=user.id,
        role=request.role,
    )
    db.add(membership_record)
    db.commit()

    log_event(
        db,
        action="create_user",
        entity_type="user",
        entity_id=user.id,
        organization_id=membership.organization_id,
        actor=membership.user.email,
    )

    return UserRead(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=membership_record.role,
        is_active=user.is_active,
    )


@router.get("/users", response_model=list[UserRead])
def list_users(
    db: Session = Depends(get_db),
    membership: OrganizationMembership = Depends(get_current_membership),
    _: None = Depends(require_permission("users:manage")),
) -> list[UserRead]:
    records = (
        db.execute(
            select(OrganizationMembership, User).where(
                OrganizationMembership.organization_id == membership.organization_id,
                OrganizationMembership.user_id == User.id,
            )
        )
        .all()
    )
    return [
        UserRead(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            role=membership_record.role,
            is_active=user.is_active,
        )
        for membership_record, user in records
    ]
