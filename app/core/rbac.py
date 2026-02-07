ROLE_ADMIN = "Administrator"
ROLE_CLINICIAN = "Clinician"
ROLE_THERAPIST = "Therapist"
ROLE_MEDICAL_PROVIDER = "Medical Provider"
ROLE_STAFF = "Staff"
ROLE_BILLING = "Billing"
ROLE_COMPLIANCE = "Compliance Manager"
ROLE_CONSULTANT = "Consultant"
ROLE_MEDICAL_ASSISTANT = "Medical Assistant"

ROLE_PERMISSIONS: dict[str, set[str]] = {
    ROLE_ADMIN: {
        "patients:read",
        "patients:write",
        "encounters:read",
        "encounters:write",
        "forms:read",
        "forms:write",
        "documents:read",
        "documents:write",
        "audit:read",
        "org:manage",
        "users:manage",
        "webhooks:manage",
    },
    ROLE_COMPLIANCE: {
        "patients:read",
        "encounters:read",
        "forms:read",
        "documents:read",
        "audit:read",
    },
    ROLE_CLINICIAN: {
        "patients:read",
        "patients:write",
        "encounters:read",
        "encounters:write",
        "forms:read",
        "forms:write",
        "documents:read",
        "documents:write",
    },
    ROLE_THERAPIST: {
        "patients:read",
        "patients:write",
        "encounters:read",
        "encounters:write",
        "forms:read",
        "forms:write",
        "documents:read",
        "documents:write",
    },
    ROLE_MEDICAL_PROVIDER: {
        "patients:read",
        "patients:write",
        "encounters:read",
        "encounters:write",
        "forms:read",
        "forms:write",
        "documents:read",
        "documents:write",
    },
    ROLE_MEDICAL_ASSISTANT: {
        "patients:read",
        "patients:write",
        "encounters:read",
        "encounters:write",
        "forms:read",
        "forms:write",
        "documents:read",
        "documents:write",
    },
    ROLE_STAFF: {
        "patients:read",
        "forms:read",
        "encounters:read",
        "documents:read",
    },
    ROLE_BILLING: {
        "patients:read",
        "encounters:read",
        "documents:read",
    },
    ROLE_CONSULTANT: {
        "patients:read",
        "encounters:read",
        "forms:read",
        "documents:read",
    },
}


def is_valid_role(role: str) -> bool:
    return role in ROLE_PERMISSIONS


def has_permission(role: str, permission: str) -> bool:
    return permission in ROLE_PERMISSIONS.get(role, set())
