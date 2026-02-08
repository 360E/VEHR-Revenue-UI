import re
from typing import Any


ALLOWED_FIELD_TYPES = {"text", "textarea", "number", "select", "checkbox", "date"}


def _slugify(value: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return normalized or "field"


def _field(field_id: str, label: str, field_type: str, *, required: bool = False, options: list[str] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": field_id,
        "label": label,
        "type": field_type,
        "required": required,
    }
    if options is not None:
        payload["options"] = options
    return payload


def _default_schema(prompt: str) -> dict[str, Any]:
    prompt_lc = prompt.lower()
    fields: list[dict[str, Any]] = []

    fields.append(_field("visit_date", "Visit Date", "date", required=True))
    fields.append(_field("chief_complaint", "Chief Complaint", "textarea", required=True))

    if any(word in prompt_lc for word in ("assessment", "audit", "behavioral", "mental", "sud")):
        fields.extend(
            [
                _field(
                    "risk_level",
                    "Risk Level",
                    "select",
                    required=True,
                    options=["Low", "Moderate", "High"],
                ),
                _field("safety_plan_present", "Safety Plan Present", "checkbox", required=False),
                _field("dimension_notes", "Dimension Notes", "textarea", required=False),
            ]
        )

    if any(word in prompt_lc for word in ("treatment", "plan", "goal", "intervention")):
        fields.extend(
            [
                _field("problem_area", "Problem Area", "text", required=True),
                _field("goal", "Goal", "textarea", required=True),
                _field("intervention", "Intervention", "textarea", required=True),
            ]
        )

    if any(word in prompt_lc for word in ("intake", "demographic", "patient")):
        fields.extend(
            [
                _field("preferred_language", "Preferred Language", "text", required=False),
                _field("housing_stability", "Housing Stability", "select", required=False, options=["Stable", "At Risk", "Unstable"]),
            ]
        )

    if len(fields) <= 2:
        fields.extend(
            [
                _field("notes", "Notes", "textarea", required=False),
                _field("follow_up_required", "Follow-up Required", "checkbox", required=False),
            ]
        )

    title = prompt.strip().splitlines()[0][:80].strip() if prompt.strip() else "Generated Form"
    if not title:
        title = "Generated Form"

    deduped_fields: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for field in fields:
        base_id = _slugify(str(field.get("id") or "field"))
        unique_id = base_id
        suffix = 2
        while unique_id in seen_ids:
            unique_id = f"{base_id}_{suffix}"
            suffix += 1
        seen_ids.add(unique_id)
        field["id"] = unique_id
        deduped_fields.append(field)

    return {
        "title": title,
        "type": "object",
        "fields": deduped_fields,
    }


def generate_schema_from_prompt(prompt: str) -> dict[str, Any]:
    text = (prompt or "").strip()
    if len(text) < 3:
        raise ValueError("Prompt must be at least 3 characters")
    schema = _default_schema(text)
    validate_generated_schema(schema)
    return schema


def validate_generated_schema(schema: dict[str, Any]) -> None:
    if not isinstance(schema, dict):
        raise ValueError("Generated schema must be an object")

    fields = schema.get("fields")
    if not isinstance(fields, list) or len(fields) == 0:
        raise ValueError("Generated schema must include a non-empty fields array")

    seen_ids: set[str] = set()
    for index, field in enumerate(fields):
        if not isinstance(field, dict):
            raise ValueError(f"Field at index {index} must be an object")

        field_id = field.get("id")
        label = field.get("label")
        field_type = field.get("type")

        if not isinstance(field_id, str) or not field_id.strip():
            raise ValueError(f"Field at index {index} is missing required 'id'")
        if not isinstance(label, str) or not label.strip():
            raise ValueError(f"Field '{field_id}' is missing required 'label'")
        if field_type not in ALLOWED_FIELD_TYPES:
            raise ValueError(f"Field '{field_id}' has unsupported type '{field_type}'")

        normalized_id = _slugify(field_id)
        if normalized_id in seen_ids:
            raise ValueError(f"Field id '{field_id}' is duplicated")
        seen_ids.add(normalized_id)

        if field_type == "select":
            options = field.get("options")
            if not isinstance(options, list) or not options:
                raise ValueError(f"Select field '{field_id}' must include options")
            if not all(isinstance(option, str) and option.strip() for option in options):
                raise ValueError(f"Select field '{field_id}' options must be non-empty strings")

