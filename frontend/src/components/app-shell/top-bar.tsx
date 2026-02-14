"use client";

import Link from "next/link";
import { ReactNode } from "react";
import { ChevronRight, Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

type TopBarProps = {
  productName: string;
  productHref?: string;
  moduleLabel?: string;
  pageTitle: string;
  subtitle?: string;
  showSearch?: boolean;
  searchPlaceholder?: string;
  searchQuery: string;
  onSearchQueryChange: (value: string) => void;
  actions?: ReactNode;
  utilitySlot?: ReactNode;
  showMobileSidebarButton?: boolean;
  onOpenMobileSidebar?: () => void;
  className?: string;
};

export function TopBar({
  productName,
  productHref,
  moduleLabel,
  pageTitle,
  subtitle,
  showSearch = false,
  searchPlaceholder = "Search",
  searchQuery,
  onSearchQueryChange,
  actions,
  utilitySlot,
  showMobileSidebarButton = false,
  onOpenMobileSidebar,
  className,
}: TopBarProps) {
  return (
    <header className={cn("ui-panel px-[var(--space-16)] py-[var(--space-12)]", className)}>
      <div className="flex flex-col gap-[var(--space-12)] lg:flex-row lg:items-center lg:justify-between">
        <div className="min-w-0 flex-1">
          <p className="flex items-center gap-[var(--space-6)] text-[11px] font-medium text-[var(--neutral-muted)]">
            {productHref ? (
              <Link
                href={productHref}
                className="rounded-[var(--radius-4)] px-[var(--space-4)] py-[2px] text-[var(--neutral-text)] transition-colors hover:bg-[var(--muted)]"
              >
                {productName}
              </Link>
            ) : (
              <span>{productName}</span>
            )}
            <ChevronRight className="h-3.5 w-3.5" aria-hidden="true" />
            <span>{moduleLabel ?? "Workspace"}</span>
          </p>

          <div className="mt-[var(--space-4)] flex items-center gap-[var(--space-8)]">
            {showMobileSidebarButton ? (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={onOpenMobileSidebar}
                className="lg:hidden"
              >
                Menu
              </Button>
            ) : null}
            <h1 className="ui-type-section-title truncate text-[var(--neutral-text)]">{pageTitle}</h1>
          </div>
          {subtitle ? (
            <p className="ui-type-body mt-[var(--space-4)] line-clamp-1 text-[var(--neutral-muted)]">{subtitle}</p>
          ) : null}
        </div>

        {showSearch ? (
          <div className="w-full lg:w-auto">
            <div className="relative w-full max-w-[420px] lg:min-w-[320px]">
              <Search className="pointer-events-none absolute left-[var(--space-12)] top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--neutral-muted)]" />
              <Input
                value={searchQuery}
                onChange={(event) => onSearchQueryChange(event.target.value)}
                placeholder={searchPlaceholder}
                aria-label="Global search"
                className="h-9 pl-[36px]"
              />
            </div>
          </div>
        ) : null}

        <div className="flex flex-wrap items-center justify-end gap-[var(--space-8)]">
          {actions ? (
            <div className="flex flex-wrap items-center gap-[var(--space-8)] border-r border-[var(--neutral-border)] pr-[var(--space-8)]">
              {actions}
            </div>
          ) : null}
          {utilitySlot ? <div className="flex flex-wrap items-center gap-[var(--space-8)]">{utilitySlot}</div> : null}
        </div>
      </div>
    </header>
  );
}
