from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ConnectorCapability:
    key: str
    label: str
    description: str


@dataclass(frozen=True)
class ConnectorDescriptor:
    key: str
    display_name: str
    category: str
    auth_modes: tuple[str, ...]
    capabilities: tuple[ConnectorCapability, ...]


class ConnectorRegistry:
    def __init__(self) -> None:
        self._connectors: dict[str, ConnectorDescriptor] = {}
        self._seed_default_connectors()

    def _seed_default_connectors(self) -> None:
        defaults = (
            ConnectorDescriptor(
                key="sharepoint",
                display_name="Microsoft SharePoint",
                category="document_storage",
                auth_modes=("oauth2",),
                capabilities=(
                    ConnectorCapability(
                        key="document_upload",
                        label="Document upload",
                        description="Store rendered PDFs and signed records in SharePoint libraries.",
                    ),
                    ConnectorCapability(
                        key="folder_sync",
                        label="Folder synchronization",
                        description="Sync encounter and patient folders with tenant-level mapping.",
                    ),
                ),
            ),
            ConnectorDescriptor(
                key="google_drive",
                display_name="Google Drive",
                category="document_storage",
                auth_modes=("oauth2",),
                capabilities=(
                    ConnectorCapability(
                        key="document_upload",
                        label="Document upload",
                        description="Upload generated files into folder structures with metadata.",
                    ),
                    ConnectorCapability(
                        key="permission_sync",
                        label="Permission sync",
                        description="Apply workspace sharing rules to clinical folders.",
                    ),
                ),
            ),
            ConnectorDescriptor(
                key="slack",
                display_name="Slack",
                category="messaging",
                auth_modes=("oauth2", "webhook"),
                capabilities=(
                    ConnectorCapability(
                        key="channel_notifications",
                        label="Channel notifications",
                        description="Push workflow alerts and high-risk audit findings to channels.",
                    ),
                ),
            ),
            ConnectorDescriptor(
                key="teams",
                display_name="Microsoft Teams",
                category="messaging",
                auth_modes=("oauth2", "webhook"),
                capabilities=(
                    ConnectorCapability(
                        key="channel_notifications",
                        label="Channel notifications",
                        description="Deliver event-driven care and compliance summaries.",
                    ),
                ),
            ),
            ConnectorDescriptor(
                key="twilio",
                display_name="Twilio",
                category="telephony",
                auth_modes=("api_key",),
                capabilities=(
                    ConnectorCapability(
                        key="sms_notifications",
                        label="SMS notifications",
                        description="Send appointment and workflow notifications.",
                    ),
                    ConnectorCapability(
                        key="voice_logging",
                        label="Voice activity logs",
                        description="Attach call outcomes to patient communication timelines.",
                    ),
                ),
            ),
            ConnectorDescriptor(
                key="quickbooks",
                display_name="QuickBooks",
                category="accounting",
                auth_modes=("oauth2",),
                capabilities=(
                    ConnectorCapability(
                        key="ledger_export",
                        label="Ledger export",
                        description="Export invoice-ready encounter and service lines.",
                    ),
                ),
            ),
            ConnectorDescriptor(
                key="xero",
                display_name="Xero",
                category="accounting",
                auth_modes=("oauth2",),
                capabilities=(
                    ConnectorCapability(
                        key="ledger_export",
                        label="Ledger export",
                        description="Publish encounter billing summaries to Xero accounts.",
                    ),
                ),
            ),
            ConnectorDescriptor(
                key="outlook_calendar",
                display_name="Outlook Calendar",
                category="scheduling",
                auth_modes=("oauth2",),
                capabilities=(
                    ConnectorCapability(
                        key="calendar_sync",
                        label="Calendar sync",
                        description="Sync encounter schedules to provider calendars.",
                    ),
                ),
            ),
            ConnectorDescriptor(
                key="google_calendar",
                display_name="Google Calendar",
                category="scheduling",
                auth_modes=("oauth2",),
                capabilities=(
                    ConnectorCapability(
                        key="calendar_sync",
                        label="Calendar sync",
                        description="Mirror appointment events and status updates.",
                    ),
                ),
            ),
            ConnectorDescriptor(
                key="docusign",
                display_name="DocuSign",
                category="esignature",
                auth_modes=("oauth2",),
                capabilities=(
                    ConnectorCapability(
                        key="signature_request",
                        label="Signature request",
                        description="Issue signature packets and track completion state.",
                    ),
                ),
            ),
            ConnectorDescriptor(
                key="okta",
                display_name="Okta",
                category="identity",
                auth_modes=("saml", "oidc"),
                capabilities=(
                    ConnectorCapability(
                        key="sso_login",
                        label="Single Sign-On",
                        description="Federated auth for workforce and partner users.",
                    ),
                ),
            ),
        )
        for connector in defaults:
            self._connectors[connector.key] = connector

    def list_connectors(self, category: str | None = None) -> list[ConnectorDescriptor]:
        values = list(self._connectors.values())
        if category:
            category = category.strip().lower()
            values = [item for item in values if item.category == category]
        return sorted(values, key=lambda item: (item.category, item.display_name))

    def get(self, key: str) -> ConnectorDescriptor | None:
        return self._connectors.get(key.strip().lower())


def _extract_from_path(payload: dict[str, Any], path: str) -> Any:
    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(part)
    return current


def transform_payload(source: dict[str, Any], field_map: dict[str, str]) -> tuple[dict[str, Any], list[str]]:
    result: dict[str, Any] = {}
    missing: list[str] = []
    for destination_field, source_path in field_map.items():
        value = _extract_from_path(source, source_path)
        if value is None:
            missing.append(destination_field)
            continue
        result[destination_field] = value
    return result, missing


connector_registry = ConnectorRegistry()
