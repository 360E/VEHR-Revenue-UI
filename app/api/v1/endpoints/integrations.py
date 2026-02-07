from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.core.deps import get_current_membership, get_current_organization, require_permission
from app.services.audit import log_event
from app.services.integrations import connector_registry, transform_payload
from app.db.session import get_db


router = APIRouter(tags=["Integrations"])


class ConnectorCapabilityRead(BaseModel):
    key: str
    label: str
    description: str


class ConnectorRead(BaseModel):
    key: str
    display_name: str
    category: str
    auth_modes: list[str]
    capabilities: list[ConnectorCapabilityRead]


class ConnectorCatalogRead(BaseModel):
    total: int
    categories: list[str]
    connectors: list[ConnectorRead]


class TransformPreviewRequest(BaseModel):
    source: dict[str, Any]
    field_map: dict[str, str] = Field(
        default_factory=dict,
        description="destination_field -> source.path mapping",
    )


class TransformPreviewRead(BaseModel):
    transformed: dict[str, Any]
    missing_fields: list[str]


def _to_connector_read(item) -> ConnectorRead:
    return ConnectorRead(
        key=item.key,
        display_name=item.display_name,
        category=item.category,
        auth_modes=list(item.auth_modes),
        capabilities=[
            ConnectorCapabilityRead(
                key=cap.key,
                label=cap.label,
                description=cap.description,
            )
            for cap in item.capabilities
        ],
    )


@router.get("/integrations/connectors", response_model=ConnectorCatalogRead)
def list_connectors(
    category: str | None = Query(None),
    organization=Depends(get_current_organization),
    _: None = Depends(require_permission("org:manage")),
) -> ConnectorCatalogRead:
    connectors = connector_registry.list_connectors(category=category)
    connector_rows = [_to_connector_read(item) for item in connectors]
    categories = sorted({item.category for item in connectors})
    return ConnectorCatalogRead(
        total=len(connector_rows),
        categories=categories,
        connectors=connector_rows,
    )


@router.get("/integrations/connectors/{connector_key}", response_model=ConnectorRead)
def get_connector(
    connector_key: str,
    organization=Depends(get_current_organization),
    _: None = Depends(require_permission("org:manage")),
) -> ConnectorRead:
    connector = connector_registry.get(connector_key)
    if not connector:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connector not found",
        )
    return _to_connector_read(connector)


@router.post("/integrations/transform/preview", response_model=TransformPreviewRead)
def preview_transform(
    payload: TransformPreviewRequest,
    db=Depends(get_db),
    organization=Depends(get_current_organization),
    membership=Depends(get_current_membership),
    _: None = Depends(require_permission("org:manage")),
) -> TransformPreviewRead:
    transformed, missing_fields = transform_payload(payload.source, payload.field_map)
    log_event(
        db,
        action="preview_integration_transform",
        entity_type="integration",
        entity_id=organization.id,
        organization_id=organization.id,
        actor=membership.user.email,
    )
    return TransformPreviewRead(
        transformed=transformed,
        missing_fields=missing_fields,
    )
