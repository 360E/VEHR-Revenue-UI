import { ModuleId } from "@/lib/modules";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

type ModuleTileCardProps = {
  moduleId: ModuleId;
  title: string;
  description: string;
  onOpen: () => void;
  isOpening?: boolean;
  testId?: string;
  className?: string;
};

const ACCENT_BAR_CLASS: Record<ModuleId, string> = {
  care_delivery: "bg-[color-mix(in_srgb,var(--status-informational)_70%,white)]",
  call_center: "bg-[color-mix(in_srgb,var(--status-stable)_70%,white)]",
  workforce: "bg-[color-mix(in_srgb,var(--status-attention)_70%,white)]",
  revenue_cycle: "bg-[color-mix(in_srgb,var(--primary)_70%,white)]",
  governance: "bg-[color-mix(in_srgb,var(--status-critical)_68%,white)]",
  administration: "bg-[color-mix(in_srgb,var(--neutral-muted)_68%,white)]",
};

const ACCENT_BADGE_CLASS: Record<ModuleId, string> = {
  care_delivery:
    "border-[color-mix(in_srgb,var(--status-informational)_34%,white)] bg-[color-mix(in_srgb,var(--status-informational)_12%,white)] text-[color-mix(in_srgb,var(--status-informational)_70%,black)]",
  call_center:
    "border-[color-mix(in_srgb,var(--status-stable)_34%,white)] bg-[color-mix(in_srgb,var(--status-stable)_12%,white)] text-[color-mix(in_srgb,var(--status-stable)_70%,black)]",
  workforce:
    "border-[color-mix(in_srgb,var(--status-attention)_34%,white)] bg-[color-mix(in_srgb,var(--status-attention)_12%,white)] text-[color-mix(in_srgb,var(--status-attention)_70%,black)]",
  revenue_cycle:
    "border-[color-mix(in_srgb,var(--primary)_34%,white)] bg-[color-mix(in_srgb,var(--primary)_12%,white)] text-[color-mix(in_srgb,var(--primary)_70%,black)]",
  governance:
    "border-[color-mix(in_srgb,var(--status-critical)_34%,white)] bg-[color-mix(in_srgb,var(--status-critical)_12%,white)] text-[color-mix(in_srgb,var(--status-critical)_70%,black)]",
  administration:
    "border-[color-mix(in_srgb,var(--neutral-muted)_34%,white)] bg-[color-mix(in_srgb,var(--neutral-muted)_14%,white)] text-[color-mix(in_srgb,var(--neutral-muted)_80%,black)]",
};

function initialsFromLabel(label: string): string {
  const parts = label.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) {
    return `${parts[0].slice(0, 1)}${parts[1].slice(0, 1)}`.toUpperCase();
  }
  return label.slice(0, 2).toUpperCase();
}

export function ModuleTileCard({
  moduleId,
  title,
  description,
  onOpen,
  isOpening = false,
  testId,
  className,
}: ModuleTileCardProps) {
  return (
    <button
      type="button"
      onClick={onOpen}
      disabled={isOpening}
      className={cn("h-full w-full rounded-xl text-left focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[var(--ring)] focus-visible:ring-offset-1", className)}
      data-testid={testId}
      aria-label={`Open ${title}`}
    >
      <Card
        className={cn(
          "relative flex h-full flex-col overflow-hidden border border-[var(--neutral-border)] bg-[var(--neutral-panel)]",
          isOpening ? "opacity-75" : "",
        )}
      >
        <span className={cn("absolute inset-x-0 top-0 h-[3px]", ACCENT_BAR_CLASS[moduleId])} aria-hidden="true" />
        <CardHeader className="pb-[var(--space-8)]">
          <div className="flex items-start gap-[var(--space-12)]">
            <span
              className={cn(
                "inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-[var(--radius-8)] border text-[length:var(--font-size-12)] font-semibold",
                ACCENT_BADGE_CLASS[moduleId],
              )}
              aria-hidden="true"
            >
              {initialsFromLabel(title)}
            </span>
            <div className="min-w-0 space-y-[var(--space-4)]">
              <CardTitle className="ui-type-section-title text-[var(--neutral-text)]">{title}</CardTitle>
              <p className="ui-type-body line-clamp-2 text-[var(--neutral-muted)]">{description}</p>
            </div>
          </div>
        </CardHeader>
        <CardContent className="mt-auto pt-0">
          <span className={cn(buttonVariants({ size: "sm" }), "pointer-events-none")}>
            {isOpening ? "Opening..." : "Open"}
          </span>
        </CardContent>
      </Card>
    </button>
  );
}
