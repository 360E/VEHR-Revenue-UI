import json
import os
from collections import Counter, defaultdict
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.deps import get_current_membership, get_current_organization, require_permission
from app.db.models.encounter import Encounter
from app.db.models.form_submission import FormSubmission
from app.db.models.form_template import FormTemplate
from app.db.models.patient import Patient
from app.db.session import get_db
from app.services.audit import log_event
from app.services.clinical_audit import run_clinical_quality_audit
from app.services.form_generation import generate_schema_from_prompt, validate_generated_schema
from app.services.outbox import enqueue_event


router = APIRouter(tags=["Forms"])


ALLOWED_TEMPLATE_STATUSES = {"draft", "published", "archived"}
DYNAMIC_FIELD_TYPES = {"text", "textarea", "number", "select", "checkbox", "date"}
TYPE_ALIASES = {
    "string": str,
    "number": (int, float),
    "integer": int,
    "boolean": bool,
    "array": list,
    "object": dict,
    "null": type(None),
}


class FormTemplateCreate(BaseModel):
    name: str
    description: str | None = Field(default=None, max_length=500)
    version: int = 1
    status: str = "draft"
    schema_json_value: str | None = Field(default=None, alias="schema_json")
    schema_payload: dict | None = Field(default=None, alias="schema")

    model_config = ConfigDict(populate_by_name=True)


class FormTemplateUpdate(BaseModel):
    name: str | None = None
    description: str | None = Field(default=None, max_length=500)
    schema_json_value: str | None = Field(default=None, alias="schema_json")
    schema_payload: dict | None = Field(default=None, alias="schema")

    model_config = ConfigDict(populate_by_name=True)


class FormTemplateRead(BaseModel):
    id: str
    name: str
    description: str | None = None
    version: int
    status: str
    schema_json_value: str = Field(alias="schema_json")
    created_at: datetime

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class FormTemplateCatalogVersion(BaseModel):
    id: str
    version: int
    status: str
    created_at: datetime


class FormTemplateCatalogRead(BaseModel):
    name: str
    latest_version: int
    published_version: int | None = None
    draft_versions: list[int]
    versions: list[FormTemplateCatalogVersion]


class FormTemplateCloneRequest(BaseModel):
    version: int | None = None
    status: str = "draft"
    name: str | None = None
    description: str | None = None


class FormTemplatePublishRequest(BaseModel):
    archive_previous_published: bool = True


class FormTemplateGenerateRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=4000)


class FormTemplateGenerateResponse(BaseModel):
    template: FormTemplateRead
    was_cloned_from_published: bool = False
    source_template_id: str


class FormSubmissionCreate(BaseModel):
    patient_id: str
    form_template_id: str | None = None
    template_version_id: str | None = None
    encounter_id: str | None = None
    submitted_data_json: str | None = None
    submitted_data: dict | None = None


class FormSubmissionRead(BaseModel):
    id: str
    patient_id: str
    encounter_id: str | None = None
    form_template_id: str
    template_version_id: str
    submitted_data_json: str
    pdf_uri: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class FormValidationRequest(BaseModel):
    submitted_data_json: str | None = None
    submitted_data: dict | None = None


class FormValidationResponse(BaseModel):
    valid: bool
    errors: list[str]
    required_fields: list[str]


def _normalize_template_status(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in ALLOWED_TEMPLATE_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid status. Expected one of: {', '.join(sorted(ALLOWED_TEMPLATE_STATUSES))}",
        )
    return normalized


def _parse_object_json(value: str, field_name: str) -> dict[str, Any]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} must be valid JSON",
        ) from exc
    if not isinstance(parsed, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} must decode to a JSON object",
        )
    return parsed


def _resolve_submission_data(payload: FormSubmissionCreate | FormValidationRequest) -> tuple[dict[str, Any], str]:
    if payload.submitted_data is not None:
        return payload.submitted_data, json.dumps(payload.submitted_data)
    if payload.submitted_data_json:
        parsed = _parse_object_json(payload.submitted_data_json, "submitted_data_json")
        return parsed, payload.submitted_data_json
    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="submitted_data_json or submitted_data is required",
    )


def _resolve_template_id(payload: FormSubmissionCreate) -> str:
    template_id = payload.template_version_id or payload.form_template_id
    if not template_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="template_version_id or form_template_id is required",
        )
    return template_id


def _template_schema(template: FormTemplate) -> dict[str, Any]:
    try:
        parsed = _parse_object_json(template.schema_json, "schema_json")
    except HTTPException as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Stored template schema is invalid for template {template.id}",
        ) from exc
    return parsed


def _matches_json_type(value: Any, type_name: str) -> bool:
    expected = TYPE_ALIASES.get(type_name)
    if expected is None:
        return True
    if type_name == "number":
        if isinstance(value, bool):
            return False
        return isinstance(value, (int, float))
    if type_name == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    return isinstance(value, expected)


def _validate_dynamic_field_schema(schema: dict[str, Any]) -> None:
    fields = schema.get("fields")
    if not isinstance(fields, list) or not fields:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Schema with 'fields' must include a non-empty fields array",
        )

    for index, raw_field in enumerate(fields):
        if not isinstance(raw_field, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Field at index {index} must be an object",
            )
        field_id = raw_field.get("id")
        label = raw_field.get("label")
        field_type = raw_field.get("type")

        if not isinstance(field_id, str) or not field_id.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Field at index {index} is missing required 'id'",
            )
        if not isinstance(label, str) or not label.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Field '{field_id}' is missing required 'label'",
            )
        if field_type not in DYNAMIC_FIELD_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Field '{field_id}' has unsupported type '{field_type}'",
            )

        if field_type == "select":
            options = raw_field.get("options")
            if not isinstance(options, list) or not options or not all(isinstance(option, str) for option in options):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Select field '{field_id}' must include string options",
                )


def _validate_template_schema_shape(schema: dict[str, Any]) -> None:
    if "fields" in schema:
        _validate_dynamic_field_schema(schema)
        return

    properties = schema.get("properties")
    if properties is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Schema must include either 'fields' or JSON-schema 'properties'",
        )
    if not isinstance(properties, dict) or not properties:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="schema_json.properties must be a non-empty object",
        )


def _resolve_template_schema_json(schema_json: str | None, schema: dict | None) -> str:
    resolved = schema_json
    if not resolved and schema is not None:
        resolved = json.dumps(schema)
    if not resolved:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="schema_json or schema is required",
        )
    parsed = _parse_object_json(resolved, "schema_json")
    _validate_template_schema_shape(parsed)
    return resolved


def _validate_data_against_dynamic_fields(schema: dict[str, Any], data: dict[str, Any]) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    required_fields: list[str] = []

    fields = schema.get("fields") or []
    for raw_field in fields:
        if not isinstance(raw_field, dict):
            continue
        field_id = str(raw_field.get("id", "")).strip()
        if not field_id:
            continue
        field_type = raw_field.get("type")
        required = bool(raw_field.get("required", False))
        if required:
            required_fields.append(field_id)

        value = data.get(field_id)
        if required and value in (None, "", []):
            errors.append(f"Missing required field: {field_id}")
            continue
        if value is None:
            continue

        if field_type in {"text", "textarea", "date", "select"} and not isinstance(value, str):
            errors.append(f"Field {field_id} must be a string")
            continue
        if field_type == "number" and not isinstance(value, (int, float)):
            errors.append(f"Field {field_id} must be a number")
            continue
        if field_type == "checkbox" and not isinstance(value, bool):
            errors.append(f"Field {field_id} must be a boolean")
            continue
        if field_type == "select":
            options = raw_field.get("options") or []
            if isinstance(options, list) and value not in options:
                errors.append(f"Field {field_id} must match one of: {', '.join(str(option) for option in options)}")

    return errors, required_fields

def _validate_data_against_schema(schema: dict[str, Any], data: dict[str, Any]) -> tuple[list[str], list[str]]:
    if "fields" in schema:
        return _validate_data_against_dynamic_fields(schema, data)

    errors: list[str] = []
    required_fields: list[str] = []
    required = schema.get("required") or []
    if isinstance(required, list):
        for field in required:
            required_fields.append(str(field))
            if field not in data or data.get(field) in (None, ""):
                errors.append(f"Missing required field: {field}")

    properties = schema.get("properties") or {}
    if not isinstance(properties, dict):
        return errors, required_fields

    for field, rules in properties.items():
        if field not in data or not isinstance(rules, dict):
            continue

        raw_type = rules.get("type")
        if isinstance(raw_type, str):
            allowed_types = [raw_type]
        elif isinstance(raw_type, list):
            allowed_types = [t for t in raw_type if isinstance(t, str)]
        else:
            allowed_types = []

        if allowed_types and not any(_matches_json_type(data[field], t) for t in allowed_types):
            errors.append(
                f"Field {field} has invalid type. Expected {', '.join(allowed_types)}"
            )
    return errors, required_fields


def _should_auto_run_clinical_audit(template: FormTemplate) -> bool:
    raw = os.getenv("CLINICAL_AUDIT_AUTO_RUN_ON_SUBMISSION", "true").strip().lower()
    if raw in {"0", "false", "no"}:
        return False
    return "assessment" in template.name.lower()


def _get_templates_by_name(templates: list[FormTemplate]) -> list[FormTemplateCatalogRead]:
    grouped: dict[str, list[FormTemplate]] = defaultdict(list)
    for template in templates:
        grouped[template.name].append(template)

    catalog: list[FormTemplateCatalogRead] = []
    for name, versions in grouped.items():
        latest_version = max(v.version for v in versions)
        published = [v.version for v in versions if v.status == "published"]
        drafts = sorted([v.version for v in versions if v.status == "draft"], reverse=True)
        catalog.append(
            FormTemplateCatalogRead(
                name=name,
                latest_version=latest_version,
                published_version=max(published) if published else None,
                draft_versions=drafts,
                versions=[
                    FormTemplateCatalogVersion(
                        id=v.id,
                        version=v.version,
                        status=v.status,
                        created_at=v.created_at,
                    )
                    for v in versions
                ],
            )
        )
    return sorted(catalog, key=lambda item: item.name.lower())


@router.get("/forms/templates", response_model=list[FormTemplateRead])
def list_form_templates(
    db: Session = Depends(get_db),
    organization=Depends(get_current_organization),
    _: None = Depends(require_permission("forms:read")),
) -> list[FormTemplateRead]:
    templates = (
        db.execute(
            select(FormTemplate)
            .where(FormTemplate.organization_id == organization.id)
            .order_by(FormTemplate.name.asc(), FormTemplate.version.desc())
        )
        .scalars()
        .all()
    )
    return templates


@router.get("/forms/templates/{template_id}", response_model=FormTemplateRead)
def get_form_template(
    template_id: str,
    db: Session = Depends(get_db),
    organization=Depends(get_current_organization),
    _: None = Depends(require_permission("forms:read")),
) -> FormTemplateRead:
    template = db.execute(
        select(FormTemplate).where(
            FormTemplate.id == template_id,
            FormTemplate.organization_id == organization.id,
        )
    ).scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form template not found")
    return template


@router.get("/forms/templates/catalog", response_model=list[FormTemplateCatalogRead])
def list_form_template_catalog(
    db: Session = Depends(get_db),
    organization=Depends(get_current_organization),
    _: None = Depends(require_permission("forms:read")),
) -> list[FormTemplateCatalogRead]:
    templates = (
        db.execute(
            select(FormTemplate)
            .where(FormTemplate.organization_id == organization.id)
            .order_by(FormTemplate.name.asc(), FormTemplate.version.desc())
        )
        .scalars()
        .all()
    )
    return _get_templates_by_name(templates)


@router.post("/forms/templates", response_model=FormTemplateRead, status_code=status.HTTP_201_CREATED)
def create_form_template(
    payload: FormTemplateCreate,
    db: Session = Depends(get_db),
    organization=Depends(get_current_organization),
    membership=Depends(get_current_membership),
    _: None = Depends(require_permission("forms:write")),
) -> FormTemplateRead:
    schema_json = _resolve_template_schema_json(payload.schema_json_value, payload.schema_payload)
    status_value = _normalize_template_status(payload.status)

    template = FormTemplate(
        organization_id=organization.id,
        name=payload.name.strip(),
        description=payload.description,
        version=payload.version,
        status=status_value,
        schema_json=schema_json,
    )
    db.add(template)
    db.commit()
    db.refresh(template)

    log_event(
        db,
        action="create_form_template",
        entity_type="form_template",
        entity_id=template.id,
        organization_id=organization.id,
        actor=membership.user.email,
    )
    enqueue_event(
        db,
        organization_id=organization.id,
        event_type="form_template.created",
        payload={
            "form_template_id": template.id,
            "name": template.name,
            "version": template.version,
            "status": template.status,
        },
    )
    return template


@router.patch("/forms/templates/{template_id}", response_model=FormTemplateRead)
def update_form_template(
    template_id: str,
    payload: FormTemplateUpdate,
    db: Session = Depends(get_db),
    organization=Depends(get_current_organization),
    membership=Depends(get_current_membership),
    _: None = Depends(require_permission("forms:manage")),
) -> FormTemplateRead:
    template = db.execute(
        select(FormTemplate).where(
            FormTemplate.id == template_id,
            FormTemplate.organization_id == organization.id,
        )
    ).scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form template not found")
    if template.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Published templates are immutable. Clone to a draft before editing.",
        )

    if payload.name is not None:
        normalized_name = payload.name.strip()
        if not normalized_name:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Template name cannot be empty")
        template.name = normalized_name
    if payload.description is not None:
        template.description = payload.description
    if payload.schema_json_value is not None or payload.schema_payload is not None:
        template.schema_json = _resolve_template_schema_json(payload.schema_json_value, payload.schema_payload)

    db.commit()
    db.refresh(template)

    log_event(
        db,
        action="update_form_template",
        entity_type="form_template",
        entity_id=template.id,
        organization_id=organization.id,
        actor=membership.user.email,
    )
    return template

@router.post("/forms/templates/{template_id}/clone", response_model=FormTemplateRead, status_code=status.HTTP_201_CREATED)
def clone_form_template(
    template_id: str,
    payload: FormTemplateCloneRequest,
    db: Session = Depends(get_db),
    organization=Depends(get_current_organization),
    membership=Depends(get_current_membership),
    _: None = Depends(require_permission("forms:manage")),
) -> FormTemplateRead:
    source = db.execute(
        select(FormTemplate).where(
            FormTemplate.id == template_id,
            FormTemplate.organization_id == organization.id,
        )
    ).scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form template not found")

    cloned_name = (payload.name or source.name).strip()
    if not cloned_name:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Template name cannot be empty")

    next_version = payload.version
    if next_version is None:
        max_version = db.execute(
            select(FormTemplate.version)
            .where(
                FormTemplate.organization_id == organization.id,
                FormTemplate.name == cloned_name,
            )
            .order_by(FormTemplate.version.desc())
            .limit(1)
        ).scalar_one_or_none()
        next_version = (max_version or 0) + 1

    status_value = _normalize_template_status(payload.status)
    cloned = FormTemplate(
        organization_id=organization.id,
        name=cloned_name,
        description=payload.description if payload.description is not None else source.description,
        version=next_version,
        status=status_value,
        schema_json=source.schema_json,
    )
    db.add(cloned)
    db.commit()
    db.refresh(cloned)

    log_event(
        db,
        action="clone_form_template",
        entity_type="form_template",
        entity_id=cloned.id,
        organization_id=organization.id,
        actor=membership.user.email,
    )
    return cloned


@router.post("/forms/templates/{template_id}/publish", response_model=FormTemplateRead)
def publish_form_template(
    template_id: str,
    payload: FormTemplatePublishRequest,
    db: Session = Depends(get_db),
    organization=Depends(get_current_organization),
    membership=Depends(get_current_membership),
    _: None = Depends(require_permission("forms:manage")),
) -> FormTemplateRead:
    template = db.execute(
        select(FormTemplate).where(
            FormTemplate.id == template_id,
            FormTemplate.organization_id == organization.id,
        )
    ).scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form template not found")

    if template.status != "draft":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only draft templates can be published.",
        )

    if payload.archive_previous_published:
        previous = (
            db.execute(
                select(FormTemplate).where(
                    FormTemplate.organization_id == organization.id,
                    FormTemplate.name == template.name,
                    FormTemplate.status == "published",
                    FormTemplate.id != template.id,
                )
            )
            .scalars()
            .all()
        )
        for record in previous:
            record.status = "archived"

    template.status = "published"
    db.commit()
    db.refresh(template)

    log_event(
        db,
        action="publish_form_template",
        entity_type="form_template",
        entity_id=template.id,
        organization_id=organization.id,
        actor=membership.user.email,
    )
    enqueue_event(
        db,
        organization_id=organization.id,
        event_type="form_template.published",
        payload={
            "form_template_id": template.id,
            "name": template.name,
            "version": template.version,
        },
    )
    return template


@router.post("/forms/templates/{template_id}/generate", response_model=FormTemplateGenerateResponse)
def generate_template_with_ai(
    template_id: str,
    payload: FormTemplateGenerateRequest,
    db: Session = Depends(get_db),
    organization=Depends(get_current_organization),
    membership=Depends(get_current_membership),
    _: None = Depends(require_permission("forms:manage")),
) -> FormTemplateGenerateResponse:
    source = db.execute(
        select(FormTemplate).where(
            FormTemplate.id == template_id,
            FormTemplate.organization_id == organization.id,
        )
    ).scalar_one_or_none()
    if not source:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form template not found")

    log_event(
        db,
        action="forms.template_generation_requested",
        entity_type="form_template",
        entity_id=source.id,
        organization_id=organization.id,
        actor=membership.user.email,
        metadata={"prompt": payload.prompt[:500]},
    )

    target = source
    was_cloned = False
    if source.status == "published":
        max_version = db.execute(
            select(FormTemplate.version)
            .where(
                FormTemplate.organization_id == organization.id,
                FormTemplate.name == source.name,
            )
            .order_by(FormTemplate.version.desc())
            .limit(1)
        ).scalar_one_or_none()
        target = FormTemplate(
            organization_id=organization.id,
            name=source.name,
            description=source.description,
            version=(max_version or 0) + 1,
            status="draft",
            schema_json=source.schema_json,
        )
        db.add(target)
        db.commit()
        db.refresh(target)
        was_cloned = True

    try:
        generated_schema = generate_schema_from_prompt(payload.prompt)
        validate_generated_schema(generated_schema)
    except ValueError as exc:
        log_event(
            db,
            action="forms.template_generation_failed",
            entity_type="form_template",
            entity_id=target.id,
            organization_id=organization.id,
            actor=membership.user.email,
            metadata={"error": str(exc)},
        )
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    target.schema_json = json.dumps(generated_schema)
    db.commit()
    db.refresh(target)

    log_event(
        db,
        action="forms.template_generation_succeeded",
        entity_type="form_template",
        entity_id=target.id,
        organization_id=organization.id,
        actor=membership.user.email,
        metadata={"was_cloned_from_published": was_cloned, "source_template_id": source.id},
    )
    log_event(
        db,
        action="forms.template_updated",
        entity_type="form_template",
        entity_id=target.id,
        organization_id=organization.id,
        actor=membership.user.email,
    )

    return FormTemplateGenerateResponse(
        template=FormTemplateRead.model_validate(target),
        was_cloned_from_published=was_cloned,
        source_template_id=source.id,
    )

@router.post("/forms/templates/{template_id}/validate-submission", response_model=FormValidationResponse)
def validate_form_submission_payload(
    template_id: str,
    payload: FormValidationRequest,
    db: Session = Depends(get_db),
    organization=Depends(get_current_organization),
    _: None = Depends(require_permission("forms:write")),
) -> FormValidationResponse:
    template = db.execute(
        select(FormTemplate).where(
            FormTemplate.id == template_id,
            FormTemplate.organization_id == organization.id,
        )
    ).scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form template not found")

    schema = _template_schema(template)
    submitted_data, _ = _resolve_submission_data(payload)
    errors, required = _validate_data_against_schema(schema, submitted_data)
    return FormValidationResponse(
        valid=not errors,
        errors=errors,
        required_fields=required,
    )


@router.post("/forms/submit", response_model=FormSubmissionRead, status_code=status.HTTP_201_CREATED)
def submit_form(
    payload: FormSubmissionCreate,
    db: Session = Depends(get_db),
    organization=Depends(get_current_organization),
    membership=Depends(get_current_membership),
    _: None = Depends(require_permission("form_submission:create")),
) -> FormSubmissionRead:
    patient = db.execute(
        select(Patient).where(
            Patient.id == payload.patient_id,
            Patient.organization_id == organization.id,
        )
    ).scalar_one_or_none()
    if not patient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Patient not found")

    template_id = _resolve_template_id(payload)
    template = db.execute(
        select(FormTemplate).where(
            FormTemplate.id == template_id,
            FormTemplate.organization_id == organization.id,
        )
    ).scalar_one_or_none()
    if not template:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Form template not found")
    if template.status != "published":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only published templates can accept submissions",
        )

    submitted_data, submitted_data_json = _resolve_submission_data(payload)
    schema = _template_schema(template)
    validation_errors, _required_fields = _validate_data_against_schema(schema, submitted_data)
    if validation_errors:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "message": "Submission failed schema validation",
                "errors": validation_errors,
            },
        )

    if payload.encounter_id:
        encounter = db.execute(
            select(Encounter).where(
                Encounter.id == payload.encounter_id,
                Encounter.organization_id == organization.id,
                Encounter.patient_id == payload.patient_id,
            )
        ).scalar_one_or_none()
        if not encounter:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Encounter not found",
            )

    submission = FormSubmission(
        organization_id=organization.id,
        patient_id=payload.patient_id,
        encounter_id=payload.encounter_id,
        form_template_id=template.id,
        submitted_data_json=submitted_data_json,
        pdf_uri=None,
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    log_event(
        db,
        action="submit_form",
        entity_type="form_submission",
        entity_id=submission.id,
        organization_id=organization.id,
        patient_id=payload.patient_id,
        actor=membership.user.email,
    )
    enqueue_event(
        db,
        organization_id=organization.id,
        event_type="form.submitted",
        payload={
            "form_submission_id": submission.id,
            "patient_id": submission.patient_id,
            "form_template_id": submission.form_template_id,
            "encounter_id": submission.encounter_id,
        },
    )

    if _should_auto_run_clinical_audit(template):
        try:
            run_clinical_quality_audit(
                db,
                organization_id=organization.id,
                subject_type="assessment",
                subject_id=submission.id,
                mode="deterministic_only",
                actor_email=membership.user.email,
                actor_user_id=membership.user.id,
            )
        except Exception as exc:  # pragma: no cover - do not block clinical submission
            log_event(
                db,
                action="clinical_audit.run_trigger_failed",
                entity_type="form_submission",
                entity_id=submission.id,
                organization_id=organization.id,
                patient_id=submission.patient_id,
                actor=membership.user.email,
                metadata={"error": str(exc)},
            )

    return FormSubmissionRead(
        id=submission.id,
        patient_id=submission.patient_id,
        encounter_id=submission.encounter_id,
        form_template_id=submission.form_template_id,
        template_version_id=submission.form_template_id,
        submitted_data_json=submission.submitted_data_json,
        pdf_uri=submission.pdf_uri,
        created_at=submission.created_at,
    )


@router.get("/patients/{patient_id}/forms", response_model=list[FormSubmissionRead])
def list_forms_for_patient(
    patient_id: str,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
    organization=Depends(get_current_organization),
    _: None = Depends(require_permission("forms:read")),
) -> list[FormSubmissionRead]:
    submissions = (
        db.execute(
            select(FormSubmission)
            .where(
                FormSubmission.patient_id == patient_id,
                FormSubmission.organization_id == organization.id,
            )
            .offset(offset)
            .limit(limit)
        )
        .scalars()
        .all()
    )
    return [
        FormSubmissionRead(
            id=submission.id,
            patient_id=submission.patient_id,
            encounter_id=submission.encounter_id,
            form_template_id=submission.form_template_id,
            template_version_id=submission.form_template_id,
            submitted_data_json=submission.submitted_data_json,
            pdf_uri=submission.pdf_uri,
            created_at=submission.created_at,
        )
        for submission in submissions
    ]


@router.get("/forms/templates/insights/usage")
def form_template_usage_insights(
    db: Session = Depends(get_db),
    organization=Depends(get_current_organization),
    _: None = Depends(require_permission("forms:read")),
) -> dict[str, Any]:
    templates = (
        db.execute(
            select(FormTemplate).where(FormTemplate.organization_id == organization.id)
        )
        .scalars()
        .all()
    )
    submissions = (
        db.execute(
            select(FormSubmission).where(FormSubmission.organization_id == organization.id)
        )
        .scalars()
        .all()
    )

    usage_counter = Counter(sub.form_template_id for sub in submissions)
    status_counter = Counter(t.status for t in templates)
    template_names = {t.id: t.name for t in templates}

    top_templates = sorted(
        (
            {
                "template_id": template_id,
                "name": template_names.get(template_id, "Unknown"),
                "submission_count": count,
            }
            for template_id, count in usage_counter.items()
        ),
        key=lambda row: row["submission_count"],
        reverse=True,
    )[:8]

    return {
        "template_count": len(templates),
        "submission_count": len(submissions),
        "status_distribution": dict(status_counter),
        "top_templates": top_templates,
    }
