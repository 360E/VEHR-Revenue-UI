import { CheckCircle2 } from "lucide-react";
import { ReactNode } from "react";

import { IntegrationIcon } from "@/components/enterprise/integration-icon";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type IntegrationStatusCardProps = {
  title: string;
  provider: "ringcentral" | "sharepoint";
  connected: boolean;
  onConnect: () => void;
  isConnecting?: boolean;
  connectLabel?: string;
  onDisconnect?: () => void;
  isDisconnecting?: boolean;
  disconnectLabel?: string;
  secondaryAction?: ReactNode;
  message?: string | null;
};

export function IntegrationStatusCard({
  title,
  provider,
  connected,
  onConnect,
  isConnecting = false,
  connectLabel = "Connect",
  onDisconnect,
  isDisconnecting = false,
  disconnectLabel = "Disconnect",
  secondaryAction,
  message,
}: IntegrationStatusCardProps) {
  return (
    <Card>
      <CardHeader className="border-b border-[color-mix(in_srgb,var(--neutral-border)_70%,white)]">
        <div className="flex items-center justify-between gap-[var(--space-8)]">
          <div className="flex min-w-0 items-center gap-[var(--space-12)]">
            <IntegrationIcon name={provider} />
            <div className="min-w-0">
              <CardTitle className="truncate">{title}</CardTitle>
            </div>
          </div>
          <Badge
            variant="outline"
            className={connected
              ? "border-[color-mix(in_srgb,var(--success)_34%,white)] bg-[color-mix(in_srgb,var(--success)_10%,white)] text-[var(--success)]"
              : "text-[var(--neutral-muted)]"}
          >
            {connected ? (
              <span className="inline-flex items-center gap-[var(--space-4)]">
                <CheckCircle2 className="h-3.5 w-3.5" />
                Connected
              </span>
            ) : "Not connected"}
          </Badge>
        </div>
      </CardHeader>
      <CardContent className="space-y-[var(--space-12)]">
        <div className="flex flex-wrap items-center gap-[var(--space-8)]">
          <Button type="button" size="sm" onClick={onConnect} disabled={isConnecting}>
            {isConnecting ? "Redirecting..." : connectLabel}
          </Button>
          {onDisconnect ? (
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onDisconnect}
              disabled={!connected || isDisconnecting}
            >
              {isDisconnecting ? "Disconnecting..." : disconnectLabel}
            </Button>
          ) : null}
          {secondaryAction}
        </div>
        {message ? <p className="ui-type-meta">{message}</p> : null}
      </CardContent>
    </Card>
  );
}
