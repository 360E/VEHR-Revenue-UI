"use client";

import { SidebarNav, type SidebarNavGroup } from "@/components/enterprise/sidebar-nav";

type ModuleSidebarProps = {
  moduleName: string;
  groups: SidebarNavGroup[];
};

export function ModuleSidebar({ moduleName, groups }: ModuleSidebarProps) {
  return (
    <div className="space-y-[var(--space-12)]">
      <div className="ui-panel px-[var(--space-16)] py-[var(--space-12)]">
        <p className="ui-type-meta font-semibold uppercase tracking-[0.14em]">Module</p>
        <p className="ui-type-body mt-[var(--space-4)] font-semibold text-[var(--neutral-text)]">{moduleName}</p>
      </div>
      <SidebarNav groups={groups} />
    </div>
  );
}
