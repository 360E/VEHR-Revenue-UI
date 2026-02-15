"use client";

import { cn } from "@/lib/utils";

export type AgentOption = {
  agent_id: string;
  display_name: string;
};

type AgentSelectorProps = {
  agents: AgentOption[];
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
  className?: string;
};

export function AgentSelector({ agents, value, onChange, disabled, className }: AgentSelectorProps) {
  return (
    <div className={cn("flex min-w-0 flex-col gap-1", className)}>
      <label className="ui-type-caption text-[10px] font-semibold uppercase tracking-[0.16em] text-[var(--neutral-muted)]">
        Agent
      </label>
      <select
        data-testid="agent-selector"
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
        className="h-9 w-full min-w-0 rounded-[var(--radius-8)] border border-[var(--neutral-border)] bg-[var(--neutral-panel)] px-3 text-sm text-[var(--neutral-text)] shadow-sm outline-none transition focus:border-[color-mix(in_srgb,var(--brand-primary)_45%,var(--neutral-border))] focus:ring-2 focus:ring-[color-mix(in_srgb,var(--brand-primary)_25%,transparent)] disabled:cursor-not-allowed disabled:opacity-60"
      >
        {agents.map((agent) => (
          <option key={agent.agent_id} value={agent.agent_id}>
            {agent.display_name}
          </option>
        ))}
      </select>
    </div>
  );
}

