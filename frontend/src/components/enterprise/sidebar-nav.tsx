import type { ReactNode } from "react";
import Link from "next/link";

import { cn } from "@/lib/utils";

export type SidebarNavItem = {
  id: string;
  label: string;
  description?: string;
  badge?: string;
  href?: string;
  external?: boolean;
  active?: boolean;
  disabled?: boolean;
  icon?: ReactNode;
  onSelect?: () => void;
  testId?: string;
};

export type SidebarNavGroup = {
  id: string;
  label: string;
  items: SidebarNavItem[];
};

type SidebarNavProps = {
  groups: SidebarNavGroup[];
  collapsed?: boolean;
  className?: string;
  testId?: string;
};

function normalizeGroupLabel(label: string): string {
  const normalized = label.replace(/[_-]+/g, " ").trim().toLowerCase();
  if (!normalized) {
    return "Section";
  }
  return `${normalized.slice(0, 1).toUpperCase()}${normalized.slice(1)}`;
}

function collapsedToken(label: string): string {
  const parts = label.trim().split(/\s+/).filter(Boolean);
  if (parts.length === 0) {
    return "N";
  }
  if (parts.length === 1) {
    return parts[0].slice(0, 2).toUpperCase();
  }
  return `${parts[0].slice(0, 1)}${parts[1].slice(0, 1)}`.toUpperCase();
}

function itemClasses(item: SidebarNavItem, collapsed: boolean): string {
  const base =
    "group relative flex min-h-[44px] w-full items-center justify-between gap-[var(--space-8)] rounded-[var(--radius-8)] border border-transparent py-[var(--space-8)] text-left transition-[background-color,border-color,box-shadow] duration-150 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--ring)] focus-visible:ring-offset-1 focus-visible:ring-offset-[var(--sidebar-bg-2)]";
  const collapseClasses = collapsed ? "justify-center px-[var(--space-6)]" : "px-[var(--space-10)]";

  if (item.disabled) {
    return cn(
      base,
      collapseClasses,
      "cursor-not-allowed text-[var(--sidebar-text-muted)] opacity-60",
    );
  }

  if (item.active) {
    return cn(
      base,
      collapseClasses,
      "bg-[var(--sidebar-item-active)] text-[var(--sidebar-text)] shadow-[var(--shadow-sm)] before:absolute before:inset-y-[6px] before:left-0 before:w-[4px] before:rounded-full before:bg-[var(--sidebar-active-bar)]",
    );
  }

  return cn(
    base,
    collapseClasses,
    "text-[var(--sidebar-text-muted)] hover:bg-[var(--sidebar-item-hover)] hover:text-[var(--sidebar-text)]",
  );
}

function SidebarNavEntry({ item, collapsed }: { item: SidebarNavItem; collapsed: boolean }) {
  const title = collapsed ? item.label : undefined;
  const compactLabel = collapsedToken(item.label);

  const content = (
    <>
      <span className={cn("min-w-0", collapsed && "text-center")}>
        {!collapsed ? (
          <>
            <span className={cn("block text-[length:var(--font-size-14)] leading-tight", item.active ? "font-semibold" : "font-medium")}>
              {item.label}
            </span>
            {item.description ? (
              <span className="mt-[2px] block text-[length:var(--font-size-12)] text-[var(--sidebar-text-muted)]">
                {item.description}
              </span>
            ) : null}
          </>
        ) : (
          <span className="text-[11px] font-semibold tracking-[0.04em] text-[var(--sidebar-text)]" aria-hidden="true">
            {compactLabel}
          </span>
        )}
      </span>

      {!collapsed && item.badge ? (
        <span className="ui-status-pill ui-status-info mt-[2px] shrink-0 whitespace-nowrap">{item.badge}</span>
      ) : null}
    </>
  );

  if (item.href && !item.disabled) {
    return (
      <Link
        href={item.href}
        target={item.external ? "_blank" : undefined}
        rel={item.external ? "noopener noreferrer" : undefined}
        className={itemClasses(item, collapsed)}
        data-testid={item.testId}
        title={title}
        aria-label={item.label}
        aria-current={item.active ? "page" : undefined}
      >
        {content}
      </Link>
    );
  }

  return (
    <button
      type="button"
      className={itemClasses(item, collapsed)}
      onClick={item.onSelect}
      disabled={item.disabled}
      data-testid={item.testId}
      title={title}
      aria-label={item.label}
      aria-current={item.active ? "page" : undefined}
    >
      {content}
    </button>
  );
}

export function SidebarNav({ groups, collapsed = false, className, testId }: SidebarNavProps) {
  return (
    <nav
      aria-label="Section navigation"
      className={cn(
        "flex flex-col gap-[var(--space-12)] rounded-[var(--radius-card)] border border-[var(--sidebar-border)] bg-[linear-gradient(180deg,var(--sidebar-bg)_0%,var(--sidebar-bg-2)_100%)] p-[var(--space-12)] shadow-[var(--shadow)]",
        collapsed && "items-center p-[var(--space-8)]",
        className,
      )}
      data-testid={testId}
      data-collapsed={collapsed ? "true" : "false"}
    >
      {groups
        .filter((group) => group.items.length > 0)
        .map((group, index) => (
          <section
            key={group.id}
            className={cn(
              "w-full space-y-[var(--space-8)]",
              index > 0 && "border-t border-[color-mix(in_srgb,var(--sidebar-text)_16%,transparent)] pt-[var(--space-12)]",
              collapsed && "space-y-[var(--space-6)]",
            )}
          >
            <h2 className={cn("px-[var(--space-8)] text-[11px] font-medium text-[var(--sidebar-text-muted)]", collapsed && "sr-only")}>
              {normalizeGroupLabel(group.label)}
            </h2>
            <ul className="space-y-[var(--space-4)]">
              {group.items.map((item) => (
                <li key={item.id}>
                  <SidebarNavEntry item={item} collapsed={collapsed} />
                </li>
              ))}
            </ul>
          </section>
        ))}
    </nav>
  );
}
