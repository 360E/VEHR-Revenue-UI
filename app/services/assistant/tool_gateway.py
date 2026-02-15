from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from collections.abc import Callable

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.time import utc_now
from app.db.models.organization_membership import OrganizationMembership
from app.services.assistant.agent_registry import AgentDefinition
from app.services.audit import log_event


@dataclass(frozen=True)
class ToolCallResult:
    tool_id: str
    status: str  # allowed|blocked|stub|error
    result: dict[str, Any] | None = None
    error: str | None = None


def _safe_json(value: Any) -> str:
    try:
        return json.dumps(value, default=str)
    except Exception:
        return str(value)


def _requires_patient_context(tool_id: str) -> bool:
    normalized = (tool_id or "").strip().lower()
    return normalized.startswith("patient.") or normalized.startswith("phi.")


def validate_tool_call(
    *,
    agent: AgentDefinition,
    role: str,
    tool_id: str,
    patient_id: str | None,
) -> tuple[bool, str | None]:
    if not agent.role_allowed(role):
        return False, "role_not_allowed"

    normalized_tool = (tool_id or "").strip()
    if not normalized_tool:
        return False, "tool_id_missing"

    if agent.allowed_tools and normalized_tool not in agent.allowed_tools:
        return False, "tool_not_allowed"

    if _requires_patient_context(normalized_tool) and not (patient_id or "").strip():
        return False, "patient_context_required"

    # Hard-block high-risk tool categories in Phase-1.
    lowered = normalized_tool.lower()
    if any(token in lowered for token in ["export", "sign", "finalize", "orgwide", "search_all_patients"]):
        return False, "high_risk_tool_blocked"

    return True, None


def execute_tool_stubbed(
    *,
    db: Session,
    membership: OrganizationMembership,
    agent: AgentDefinition,
    tool_id: str,
    args: dict[str, Any] | None,
    patient_id: str | None,
    workstation_id: str | None,
) -> ToolCallResult:
    allowed, reason = validate_tool_call(
        agent=agent,
        role=membership.role,
        tool_id=tool_id,
        patient_id=patient_id,
    )

    log_event(
        db,
        action="assistant_tool_attempt",
        entity_type="assistant_tool",
        entity_id=tool_id or "unknown",
        organization_id=membership.organization_id,
        patient_id=patient_id,
        actor=membership.user.email,
        metadata={
            "user_id": membership.user_id,
            "org_id": membership.organization_id,
            "role": membership.role,
            "agent_id": agent.agent_id,
            "tool_id": tool_id,
            "allowed": allowed,
            "reason": reason,
            "args_json": _safe_json(args or {}),
            "workstation_id": workstation_id,
            "attempted_at": utc_now().isoformat(),
        },
    )

    if not allowed:
        return ToolCallResult(tool_id=tool_id, status="blocked", error=reason or "blocked")

    # Phase-1: default to stubbed responses unless a tool is explicitly implemented elsewhere.
    return ToolCallResult(tool_id=tool_id, status="stub", result={"ok": False, "detail": "stubbed_phase_1"})


def execute_tool(
    *,
    db: Session,
    membership: OrganizationMembership,
    agent: AgentDefinition,
    tool_id: str,
    args: dict[str, Any] | None,
    patient_id: str | None,
    workstation_id: str | None,
    executor: Callable[[], dict[str, Any]] | None = None,
) -> ToolCallResult:
    result = execute_tool_stubbed(
        db=db,
        membership=membership,
        agent=agent,
        tool_id=tool_id,
        args=args,
        patient_id=patient_id,
        workstation_id=workstation_id,
    )
    if result.status != "stub" or executor is None:
        return result
    try:
        payload = executor()
    except HTTPException as exc:
        return ToolCallResult(tool_id=tool_id, status="error", error=str(exc.detail))
    except Exception as exc:
        return ToolCallResult(tool_id=tool_id, status="error", error=str(exc))
    return ToolCallResult(tool_id=tool_id, status="allowed", result=payload)


def require_tool_allowed(result: ToolCallResult) -> None:
    if result.status == "blocked":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=result.error or "tool_blocked")
    if result.status == "error":
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=result.error or "tool_error")
