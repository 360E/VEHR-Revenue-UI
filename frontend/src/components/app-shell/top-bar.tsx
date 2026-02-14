"use client";

import Link from "next/link";
import { ReactNode } from "react";
import { ChevronRight, Search } from "lucide-react";

import { BrandLogo } from "@/components/brand/brand-logo";
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
  const brandNode = productHref ? (
    <Link
      href={productHref}
      data-testid="topbar-brand"
      className="inline-flex flex-none items-center gap-[var(--space-8)] whitespace-nowrap rounded-full bg-[var(--brand-primary-50)] px-[var(--space-12)] py-[var(--space-6)] text-[15px] font-bold text-[var(--brand-primary-600)] shadow-[inset_0_0_0_1px_color-mix(in_srgb,var(--brand-primary)_18%,white)] transition-colors hover:bg-[color-mix(in_srgb,var(--brand-primary-50)_72%,white)]"
    >
      <BrandLogo size={20} />
      <span>{productName}</span>
    </Link>
  ) : (
    <span
      data-testid="topbar-brand"
      className="inline-flex flex-none items-center gap-[var(--space-8)] whitespace-nowrap rounded-full bg-[var(--brand-primary-50)] px-[var(--space-12)] py-[var(--space-6)] text-[15px] font-bold text-[var(--brand-primary-600)] shadow-[inset_0_0_0_1px_color-mix(in_srgb,var(--brand-primary)_18%,white)]"
    >
      <BrandLogo size={20} />
      <span>{productName}</span>
    </span>
  );

  return (
    <header
      className={cn(
        "ui-panel relative overflow-hidden border-[var(--border)] bg-[linear-gradient(180deg,var(--surface)_0%,color-mix(in_srgb,var(--brand-primary-50)_46%,white)_100%)] px-[var(--space-16)] py-[var(--space-12)] shadow-[var(--shadow)] before:absolute before:inset-x-0 before:top-0 before:h-1 before:bg-[var(--brand-primary)]",
        className,
      )}
    >
      <div className="relative z-10 flex flex-col gap-[var(--space-12)]">
        <div className="flex flex-wrap items-center justify-between gap-[var(--space-8)]">
          <p className="flex min-w-0 flex-wrap items-center gap-[var(--space-6)] text-[11px] font-medium text-[var(--neutral-muted)]">
            {brandNode}
            <ChevronRight className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
            <span className="truncate">{moduleLabel ?? "Workspace"}</span>
          </p>
          {utilitySlot ? <div className="flex flex-wrap items-center gap-[var(--space-8)]">{utilitySlot}</div> : null}
        </div>

        <div className="flex flex-col gap-[var(--space-12)] lg:flex-row lg:items-center lg:justify-between">
          <div className="min-w-0 flex-1">
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

          <div className="flex min-w-0 flex-1 items-center justify-end gap-[var(--space-8)]">
            {showSearch ? (
              <div className="relative min-w-[240px] flex-1 lg:max-w-[540px]">
                <Search className="pointer-events-none absolute left-[var(--space-12)] top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--neutral-muted)]" />
                <Input
                  value={searchQuery}
                  onChange={(event) => onSearchQueryChange(event.target.value)}
                  placeholder={searchPlaceholder}
                  aria-label="Global search"
                  className="h-9 pl-[36px]"
                />
              </div>
            ) : null}
            {actions ? <div className="flex flex-wrap items-center gap-[var(--space-8)]">{actions}</div> : null}
          </div>
        </div>
      </div>
    </header>
  );
}
