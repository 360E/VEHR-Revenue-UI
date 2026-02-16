from __future__ import annotations

from dataclasses import dataclass
from typing import FrozenSet


ALL_ROLES = "*"


@dataclass(frozen=True)
class AgentDefinition:
    agent_id: str
    display_name: str
    allowed_roles: FrozenSet[str]
    allowed_tools: FrozenSet[str]
    allowed_domains: FrozenSet[str]
    actions_allowed: FrozenSet[str]

    def role_allowed(self, role: str) -> bool:
        normalized = (role or "").strip().lower()
        if not normalized:
            return False
        return ALL_ROLES in self.allowed_roles or normalized in self.allowed_roles


_DEFAULT_AGENTS: dict[str, AgentDefinition] = {
    "enterprise_copilot": AgentDefinition(
        agent_id="enterprise_copilot",
        display_name="Enterprise Copilot",
        allowed_roles=frozenset({ALL_ROLES}),
        allowed_tools=frozenset(
            {
                # Phase-1 tools. External integrations should remain stubbed until explicitly enabled.
                "memory.set",
                "memory.delete",
                "reminder.create",
                "reminder.update",
                # Microsoft 365 reminder channels (draft-only).
                "ms.todo.task.create_draft",
                "ms.outlook.event.create_draft",
            }
        ),
        allowed_domains=frozenset({"enterprise"}),
        actions_allowed=frozenset({"draft_only"}),
    ),
    # Keep a legacy agent id for internal/testing parity with existing ai_copilot logic.
    "legacy_copilot": AgentDefinition(
        agent_id="legacy_copilot",
        display_name="Legacy Copilot",
        allowed_roles=frozenset({ALL_ROLES}),
        allowed_tools=frozenset(),
        allowed_domains=frozenset({"legacy"}),
        actions_allowed=frozenset({"draft_only"}),
    ),
}


def get_agent(agent_id: str) -> AgentDefinition | None:
    return _DEFAULT_AGENTS.get((agent_id or "").strip())


def list_agents_for_role(role: str) -> list[AgentDefinition]:
    return [agent for agent in _DEFAULT_AGENTS.values() if agent.role_allowed(role)]
