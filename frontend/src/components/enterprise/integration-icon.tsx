import { Building2, Phone } from "lucide-react";

import { cn } from "@/lib/utils";

type IntegrationIconName = "ringcentral" | "sharepoint";

type IntegrationIconProps = {
  name: IntegrationIconName;
  className?: string;
};

export function IntegrationIcon({ name, className }: IntegrationIconProps) {
  const common = "inline-flex h-10 w-10 items-center justify-center rounded-[var(--radius-8)] border";

  if (name === "ringcentral") {
    return (
      <span
        className={cn(
          common,
          "border-[color-mix(in_srgb,var(--status-stable)_30%,white)] bg-[color-mix(in_srgb,var(--status-stable)_10%,white)] text-[color-mix(in_srgb,var(--status-stable)_72%,black)]",
          className,
        )}
        aria-hidden="true"
      >
        <Phone className="h-4 w-4" />
      </span>
    );
  }

  return (
    <span
      className={cn(
        common,
        "border-[color-mix(in_srgb,var(--status-informational)_30%,white)] bg-[color-mix(in_srgb,var(--status-informational)_10%,white)] text-[color-mix(in_srgb,var(--status-informational)_72%,black)]",
        className,
      )}
      aria-hidden="true"
    >
      <Building2 className="h-4 w-4" />
    </span>
  );
}
