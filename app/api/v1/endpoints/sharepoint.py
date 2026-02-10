import os
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from app.core.deps import get_current_membership
from app.db.models.organization_membership import OrganizationMembership


router = APIRouter(tags=["SharePoint"])

DEFAULT_SHAREPOINT_HOME_URL = (
    "https://valleyhealthandcounseling.sharepoint.com/sites/ValleyHealthHomePage"
)
ALLOWED_SHAREPOINT_HOST = "sharepoint.com"


class SharePointHomeResponse(BaseModel):
    organization_id: str
    home_url: str


def _is_allowed_sharepoint_host(hostname: str) -> bool:
    normalized = hostname.strip().lower().rstrip(".")
    return normalized == ALLOWED_SHAREPOINT_HOST or normalized.endswith(
        f".{ALLOWED_SHAREPOINT_HOST}"
    )


def _validate_sharepoint_url(raw_url: str) -> str:
    candidate = raw_url.strip()
    parsed = urlparse(candidate)
    if parsed.scheme != "https":
        raise ValueError("SharePoint URL must use https")
    if not parsed.hostname:
        raise ValueError("SharePoint URL must include a hostname")
    if not _is_allowed_sharepoint_host(parsed.hostname):
        raise ValueError("SharePoint URL host must be a sharepoint.com domain")
    return candidate


def _resolve_sharepoint_home_url(*, organization_id: str) -> str:
    # Organization-level settings table does not currently exist; env/default only for now.
    configured = os.getenv("SHAREPOINT_HOME_URL", "").strip()
    candidate = configured or DEFAULT_SHAREPOINT_HOME_URL
    return _validate_sharepoint_url(candidate)


@router.get("/sharepoint/home", response_model=SharePointHomeResponse)
def sharepoint_home(
    membership: OrganizationMembership = Depends(get_current_membership),
) -> SharePointHomeResponse:
    try:
        home_url = _resolve_sharepoint_home_url(organization_id=membership.organization_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Invalid SharePoint configuration: {exc}",
        )

    return SharePointHomeResponse(
        organization_id=membership.organization_id,
        home_url=home_url,
    )
