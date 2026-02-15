import os

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.rbac import has_permission_for_organization
from app.core.security import TokenData, decode_access_token
from app.db.models.organization import Organization
from app.db.models.organization_membership import OrganizationMembership
from app.db.models.user import User
from app.db.session import get_db

auth_scheme = HTTPBearer(auto_error=False)
SSE_QUERY_TOKEN_COMPAT_ENV = "FEATURE_SSE_QUERY_TOKEN_COMPAT"
COOKIE_JWT_KEYS: tuple[str, ...] = ("vehr_access_token", "access_token")


def _truthy_env(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "on"}


def extract_jwt_from_request(
    *,
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
) -> tuple[str | None, str | None]:
    query_token = (request.query_params.get("access_token") or "").strip()
    if query_token:
        # Optional transition-only fallback. Do NOT enable in production.
        if _truthy_env(SSE_QUERY_TOKEN_COMPAT_ENV):
            return query_token, "query_param"
        return None, "query_param_blocked"

    # Prefer Authorization header when present (non-browser clients can send it for SSE).
    if credentials is not None and credentials.credentials:
        return credentials.credentials, "authorization"

    # Browser SSE: cookies with withCredentials=true.
    for key in COOKIE_JWT_KEYS:
        cookie_token = (request.cookies.get(key) or "").strip()
        if cookie_token:
            return cookie_token, "cookie"

    return None, None


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(auth_scheme),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing credentials",
        )

    try:
        token_data: TokenData = decode_access_token(credentials.credentials)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    user = db.get(User, token_data.user_id)
    if not user or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user",
        )
    return user


def get_current_membership(
    credentials: HTTPAuthorizationCredentials = Depends(auth_scheme),
    db: Session = Depends(get_db),
) -> OrganizationMembership:
    if credentials is None or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing credentials",
        )

    try:
        token_data: TokenData = decode_access_token(credentials.credentials)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )

    membership = db.execute(
        select(OrganizationMembership).where(
            OrganizationMembership.user_id == token_data.user_id,
            OrganizationMembership.organization_id == token_data.organization_id,
        )
    ).scalar_one_or_none()
    if not membership:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization access denied",
        )
    if not membership.user or not membership.user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user",
        )
    return membership


def get_current_organization(
    membership: OrganizationMembership = Depends(get_current_membership),
    db: Session = Depends(get_db),
) -> Organization:
    organization = db.get(Organization, membership.organization_id)
    if not organization:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Organization not found",
        )
    return organization


def require_permission(permission: str):
    def _require(
        membership: OrganizationMembership = Depends(get_current_membership),
        db: Session = Depends(get_db),
    ) -> None:
        if not has_permission_for_organization(
            db,
            organization_id=membership.organization_id,
            role=membership.role,
            permission=permission,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )

    return _require


def get_current_membership_sse(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(auth_scheme),
    db: Session = Depends(get_db),
) -> OrganizationMembership:
    token, source = extract_jwt_from_request(request=request, credentials=credentials)
    if token is None and source == "query_param_blocked":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="query_token_not_allowed")
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing credentials")

    try:
        token_data: TokenData = decode_access_token(token)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    membership = db.execute(
        select(OrganizationMembership).where(
            OrganizationMembership.user_id == token_data.user_id,
            OrganizationMembership.organization_id == token_data.organization_id,
        )
    ).scalar_one_or_none()
    if not membership:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Organization access denied")
    if not membership.user or not membership.user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Inactive user")
    if not has_permission_for_organization(
        db,
        organization_id=membership.organization_id,
        role=membership.role,
        permission="tasks:read_self",
    ):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")

    # Stash for endpoint-level auditing (avoid returning token metadata to callers).
    try:
        setattr(request.state, "sse_auth_source", source)
    except Exception:
        pass

    return membership
