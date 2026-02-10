from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.deps import get_current_membership, require_permission
from app.db.models.organization_membership import OrganizationMembership
from app.db.session import get_db
from app.services.audit import log_event
from app.services.microsoft_graph import (
    MicrosoftGraphServiceError,
    get_sharepoint_item_metadata,
    get_sharepoint_item_download,
    list_sharepoint_children,
    list_sharepoint_drives,
    search_sharepoint_sites,
)


router = APIRouter(tags=["SharePoint"])


class SharePointSiteRead(BaseModel):
    id: str
    name: str
    web_url: str


class SharePointDriveRead(BaseModel):
    id: str
    name: str
    web_url: str


class SharePointItemRead(BaseModel):
    id: str
    name: str
    is_folder: bool
    size: int | None = None
    web_url: str
    last_modified_date_time: str | None = None
    mime_type: str | None = None


class SharePointItemPreviewRead(BaseModel):
    id: str
    name: str
    web_url: str
    mime_type: str | None = None
    preview_kind: str
    is_previewable: bool
    download_url: str | None = None


def _raise_graph_error(exc: MicrosoftGraphServiceError) -> None:
    raise HTTPException(
        status_code=exc.status_code,
        detail=exc.detail,
    ) from exc


@router.get("/sharepoint/sites", response_model=list[SharePointSiteRead])
def sharepoint_sites(
    search: str = Query(default=""),
    db: Session = Depends(get_db),
    membership: OrganizationMembership = Depends(get_current_membership),
    _: None = Depends(require_permission("org:manage")),
) -> list[SharePointSiteRead]:
    try:
        rows = search_sharepoint_sites(
            db=db,
            organization_id=membership.organization_id,
            user_id=membership.user_id,
            search=search,
        )
    except MicrosoftGraphServiceError as exc:
        _raise_graph_error(exc)

    log_event(
        db,
        action="sharepoint.sites.list",
        entity_type="sharepoint",
        entity_id=membership.organization_id,
        organization_id=membership.organization_id,
        actor=membership.user.email,
        metadata={"search": search},
    )

    return [
        SharePointSiteRead(
            id=row.id,
            name=row.name,
            web_url=row.web_url,
        )
        for row in rows
    ]


@router.get("/sharepoint/sites/{site_id}/drives", response_model=list[SharePointDriveRead])
def sharepoint_site_drives(
    site_id: str,
    db: Session = Depends(get_db),
    membership: OrganizationMembership = Depends(get_current_membership),
    _: None = Depends(require_permission("org:manage")),
) -> list[SharePointDriveRead]:
    try:
        rows = list_sharepoint_drives(
            db=db,
            organization_id=membership.organization_id,
            user_id=membership.user_id,
            site_id=site_id,
        )
    except MicrosoftGraphServiceError as exc:
        _raise_graph_error(exc)

    log_event(
        db,
        action="sharepoint.drives.list",
        entity_type="sharepoint_site",
        entity_id=site_id,
        organization_id=membership.organization_id,
        actor=membership.user.email,
    )

    return [
        SharePointDriveRead(
            id=row.id,
            name=row.name,
            web_url=row.web_url,
        )
        for row in rows
    ]


@router.get("/sharepoint/drives/{drive_id}/root/children", response_model=list[SharePointItemRead])
def sharepoint_drive_root_children(
    drive_id: str,
    db: Session = Depends(get_db),
    membership: OrganizationMembership = Depends(get_current_membership),
    _: None = Depends(require_permission("org:manage")),
) -> list[SharePointItemRead]:
    try:
        rows = list_sharepoint_children(
            db=db,
            organization_id=membership.organization_id,
            user_id=membership.user_id,
            drive_id=drive_id,
            item_id=None,
        )
    except MicrosoftGraphServiceError as exc:
        _raise_graph_error(exc)

    log_event(
        db,
        action="sharepoint.items.list",
        entity_type="sharepoint_drive",
        entity_id=drive_id,
        organization_id=membership.organization_id,
        actor=membership.user.email,
        metadata={"scope": "root"},
    )

    return [
        SharePointItemRead(
            id=row.id,
            name=row.name,
            is_folder=row.is_folder,
            size=row.size,
            web_url=row.web_url,
            last_modified_date_time=row.last_modified,
            mime_type=row.mime_type,
        )
        for row in rows
    ]


@router.get("/sharepoint/drives/{drive_id}/items/{item_id}/children", response_model=list[SharePointItemRead])
def sharepoint_drive_item_children(
    drive_id: str,
    item_id: str,
    db: Session = Depends(get_db),
    membership: OrganizationMembership = Depends(get_current_membership),
    _: None = Depends(require_permission("org:manage")),
) -> list[SharePointItemRead]:
    try:
        rows = list_sharepoint_children(
            db=db,
            organization_id=membership.organization_id,
            user_id=membership.user_id,
            drive_id=drive_id,
            item_id=item_id,
        )
    except MicrosoftGraphServiceError as exc:
        _raise_graph_error(exc)

    log_event(
        db,
        action="sharepoint.items.list",
        entity_type="sharepoint_item",
        entity_id=item_id,
        organization_id=membership.organization_id,
        actor=membership.user.email,
        metadata={"drive_id": drive_id},
    )

    return [
        SharePointItemRead(
            id=row.id,
            name=row.name,
            is_folder=row.is_folder,
            size=row.size,
            web_url=row.web_url,
            last_modified_date_time=row.last_modified,
            mime_type=row.mime_type,
        )
        for row in rows
    ]


@router.get("/sharepoint/items/{item_id}/preview", response_model=SharePointItemPreviewRead)
def sharepoint_item_preview(
    item_id: str,
    drive_id: str = Query(...),
    db: Session = Depends(get_db),
    membership: OrganizationMembership = Depends(get_current_membership),
    _: None = Depends(require_permission("org:manage")),
) -> SharePointItemPreviewRead:
    try:
        item = get_sharepoint_item_metadata(
            db=db,
            organization_id=membership.organization_id,
            user_id=membership.user_id,
            drive_id=drive_id,
            item_id=item_id,
        )
    except MicrosoftGraphServiceError as exc:
        _raise_graph_error(exc)

    if item.is_folder:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Folders do not support preview",
        )

    mime = (item.mime_type or "").lower()
    is_pdf = mime == "application/pdf" or item.name.lower().endswith(".pdf")
    is_image = mime.startswith("image/")
    preview_kind = "pdf" if is_pdf else "image" if is_image else "external"
    is_previewable = preview_kind in {"pdf", "image"}

    log_event(
        db,
        action="sharepoint.preview",
        entity_type="sharepoint_item",
        entity_id=item_id,
        organization_id=membership.organization_id,
        actor=membership.user.email,
        metadata={"drive_id": drive_id, "preview_kind": preview_kind},
    )

    download_url = None
    if is_previewable:
        download_url = f"/api/v1/sharepoint/items/{item_id}/download?drive_id={drive_id}"

    return SharePointItemPreviewRead(
        id=item.id,
        name=item.name,
        web_url=item.web_url,
        mime_type=item.mime_type,
        preview_kind=preview_kind,
        is_previewable=is_previewable,
        download_url=download_url,
    )


@router.get("/sharepoint/items/{item_id}/download")
def sharepoint_item_download(
    item_id: str,
    drive_id: str = Query(...),
    db: Session = Depends(get_db),
    membership: OrganizationMembership = Depends(get_current_membership),
    _: None = Depends(require_permission("org:manage")),
) -> StreamingResponse:
    try:
        payload = get_sharepoint_item_download(
            db=db,
            organization_id=membership.organization_id,
            user_id=membership.user_id,
            drive_id=drive_id,
            item_id=item_id,
        )
    except MicrosoftGraphServiceError as exc:
        _raise_graph_error(exc)

    log_event(
        db,
        action="sharepoint.download",
        entity_type="sharepoint_item",
        entity_id=item_id,
        organization_id=membership.organization_id,
        actor=membership.user.email,
        metadata={"drive_id": drive_id},
    )

    headers = {
        "Content-Disposition": f'inline; filename="{payload.filename}"',
        "Cache-Control": "no-store",
    }
    if payload.content_length is not None:
        headers["Content-Length"] = str(payload.content_length)
    if payload.web_url:
        headers["X-SharePoint-Web-Url"] = payload.web_url

    return StreamingResponse(
        payload.stream,
        media_type=payload.content_type or "application/octet-stream",
        headers=headers,
        status_code=status.HTTP_200_OK,
    )


@router.get("/sharepoint/drives/{drive_id}/items/{item_id}/download")
def sharepoint_drive_item_download(
    drive_id: str,
    item_id: str,
    db: Session = Depends(get_db),
    membership: OrganizationMembership = Depends(get_current_membership),
    _: None = Depends(require_permission("org:manage")),
) -> StreamingResponse:
    try:
        payload = get_sharepoint_item_download(
            db=db,
            organization_id=membership.organization_id,
            user_id=membership.user_id,
            drive_id=drive_id,
            item_id=item_id,
        )
    except MicrosoftGraphServiceError as exc:
        _raise_graph_error(exc)

    log_event(
        db,
        action="sharepoint.download",
        entity_type="sharepoint_item",
        entity_id=item_id,
        organization_id=membership.organization_id,
        actor=membership.user.email,
        metadata={"drive_id": drive_id},
    )

    headers = {
        "Content-Disposition": f'inline; filename="{payload.filename}"',
        "Cache-Control": "no-store",
    }
    if payload.content_length is not None:
        headers["Content-Length"] = str(payload.content_length)
    if payload.web_url:
        headers["X-SharePoint-Web-Url"] = payload.web_url

    return StreamingResponse(
        payload.stream,
        media_type=payload.content_type or "application/octet-stream",
        headers=headers,
        status_code=status.HTTP_200_OK,
    )
