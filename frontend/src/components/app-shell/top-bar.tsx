"use client";

import { ReactNode } from "react";
import { Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";

type TopBarProps = {
  productName: string;
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
    <header className={cn("ui-panel p-[var(--space-16)]", className)}>
      <div className="flex flex-col gap-[var(--space-12)]">
        <div className="flex flex-wrap items-start justify-between gap-[var(--space-12)]">
          <div className="min-w-0">
            <p className="ui-type-meta font-semibold uppercase tracking-[0.14em]">{productName}</p>
            <h1 className="ui-type-section-title mt-[var(--space-4)] text-[var(--neutral-text)]">{pageTitle}</h1>
            {subtitle ? (
              <p className="ui-type-body mt-[var(--space-4)] text-[var(--neutral-muted)]">{subtitle}</p>
            ) : null}
          </div>

          <div className="flex min-w-[260px] flex-1 flex-wrap items-center justify-end gap-[var(--space-8)]">
            {showMobileSidebarButton ? (
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={onOpenMobileSidebar}
                className="lg:hidden"
              >
                Module Menu
              </Button>
            ) : null}

            {showSearch ? (
              <div className="relative w-full max-w-[320px]">
                <Search className="pointer-events-none absolute left-[var(--space-12)] top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--neutral-muted)]" />
                <Input
                  value={searchQuery}
                  onChange={(event) => onSearchQueryChange(event.target.value)}
                  placeholder={searchPlaceholder}
                  aria-label="Global search"
                  className="h-[var(--space-32)] pl-[36px]"
                />
              </div>
            ) : null}

            {actions ? <div className="flex flex-wrap items-center gap-[var(--space-8)]">{actions}</div> : null}

            {utilitySlot ? <div className="flex flex-wrap items-center gap-[var(--space-8)]">{utilitySlot}</div> : null}
          </div>
        </div>
      </div>
    </header>
  );
}
