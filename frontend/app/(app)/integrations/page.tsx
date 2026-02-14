"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";

import { IntegrationStatusCard } from "@/components/enterprise/integration-status-card";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import MetricCard from "../_components/MetricCard";
import { apiFetch, buildUrl } from "@/lib/api";
import { AppLayoutPageConfig } from "@/lib/app-layout-config";

type ConnectorCapability = {
  key: string;
  label: string;
  description: string;
};

type Connector = {
  key: string;
  display_name: string;
  category: string;
  auth_modes: string[];
  capabilities: ConnectorCapability[];
};

type ConnectorCatalog = {
  total: number;
  categories: string[];
  connectors: Connector[];
};

type MicrosoftConnectResponse = {
  authorization_url: string;
};

type RingCentralStatus = {
  connected: boolean;
  rc_account_id?: string | null;
};

export default function IntegrationsPage() {
  const searchParams = useSearchParams();
  const [catalog, setCatalog] = useState<ConnectorCatalog | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isConnectingMicrosoft, setIsConnectingMicrosoft] = useState(false);
  const [microsoftConnectError, setMicrosoftConnectError] = useState<string | null>(null);
  const [ringCentralStatus, setRingCentralStatus] = useState<RingCentralStatus | null>(null);
  const [isConnectingRingCentral, setIsConnectingRingCentral] = useState(false);
  const [ringCentralError, setRingCentralError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function load() {
      try {
        setError(null);
        const [data, status] = await Promise.all([
          apiFetch<ConnectorCatalog>("/api/v1/integrations/connectors", {
            cache: "no-store",
          }),
          apiFetch<RingCentralStatus>("/api/v1/integrations/ringcentral/status", {
            cache: "no-store",
          }),
        ]);
        if (!isMounted) return;
        setCatalog(data);
        setRingCentralStatus(status);
      } catch (err) {
        if (!isMounted) return;
        setError(err instanceof Error ? err.message : "Failed to load connector catalog");
      }
    }

    load();
    return () => {
      isMounted = false;
    };
  }, []);

  useEffect(() => {
    const connected = searchParams.get("connected");
    if (connected === "1") {
      setRingCentralError(null);
      return;
    }
    if (connected === "0") {
      setRingCentralError("RingCentral connection could not be completed. Please try again.");
    }
  }, [searchParams]);

  const connectors = catalog?.connectors ?? [];

  async function handleConnectMicrosoft() {
    setMicrosoftConnectError(null);
    setIsConnectingMicrosoft(true);
    try {
      const response = await apiFetch<MicrosoftConnectResponse>(
        "/api/v1/integrations/microsoft/connect",
        { cache: "no-store" },
      );
      if (!response.authorization_url) {
        throw new Error("Microsoft authorization URL was not returned.");
      }
      window.location.assign(response.authorization_url);
    } catch {
      setMicrosoftConnectError("Unable to start Microsoft connection.");
      setIsConnectingMicrosoft(false);
    }
  }

  async function handleConnectRingCentral() {
    setRingCentralError(null);
    setIsConnectingRingCentral(true);
    try {
      const returnTo = `${window.location.origin}/integrations`;
      const connectUrl = `${buildUrl("/api/v1/integrations/ringcentral/connect")}?return_to=${encodeURIComponent(returnTo)}`;
      window.location.assign(connectUrl);
    } catch {
      setRingCentralError("Unable to start RingCentral connection.");
      setIsConnectingRingCentral(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <AppLayoutPageConfig
        moduleLabel="System"
        pageTitle="Integrations"
        subtitle="Connect third-party systems without exposing technical metadata."
      />

      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="space-y-2">
          <h1 className="text-3xl font-semibold tracking-tight text-slate-900">Connected Systems</h1>
          <p className="text-sm text-slate-600">
            Manage organization-level integrations in a simplified view.
          </p>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <IntegrationStatusCard
          title="RingCentral"
          provider="ringcentral"
          connected={Boolean(ringCentralStatus?.connected)}
          onConnect={() => void handleConnectRingCentral()}
          isConnecting={isConnectingRingCentral}
          connectLabel="Connect RingCentral"
          message={ringCentralError}
        />

        <IntegrationStatusCard
          title="Microsoft SharePoint"
          provider="sharepoint"
          connected={false}
          onConnect={() => void handleConnectMicrosoft()}
          isConnecting={isConnectingMicrosoft}
          connectLabel="Connect Microsoft"
          message={microsoftConnectError}
          secondaryAction={(
            <Button type="button" variant="outline" size="sm" asChild>
              <Link href="/admin/integrations/microsoft">Open</Link>
            </Button>
          )}
        />
      </div>


      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard label="Connectors" value={`${catalog?.total ?? 0}`} hint="Available adapters" />
        <MetricCard
          label="Categories"
          value={`${catalog?.categories.length ?? 0}`}
          hint="Integration domains"
        />
        <MetricCard
          label="Framework"
          value="Active"
          hint="Discovery + mapping preview live"
        />
      </div>

      {error ? (
        <Card className="border-rose-200 bg-rose-50/80">
          <CardContent className="pt-6 text-sm text-rose-700">{error}</CardContent>
        </Card>
      ) : null}

      <Card className="border-slate-200/70 shadow-sm">
        <CardHeader className="border-b border-slate-200/70 bg-slate-50/70">
          <CardTitle className="text-base text-slate-900">Catalog categories</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2 pt-5">
          {(catalog?.categories ?? []).map((category) => (
            <span key={category} className="ui-status-pill ui-status-info">{category.replace("_", " ")}</span>
          ))}
        </CardContent>
      </Card>

      <div className="grid gap-4 lg:grid-cols-2">
        {connectors.map((connector) => (
          <Card key={connector.key} className="border-slate-200/70 shadow-sm">
            <CardHeader className="border-b border-slate-200/70 bg-slate-50/70">
              <div className="flex items-center justify-between gap-3">
                <CardTitle className="text-base text-slate-900">{connector.display_name}</CardTitle>
                <span className="ui-status-pill ui-status-info">
                  {connector.category.replace("_", " ")}
                </span>
              </div>
            </CardHeader>
            <CardContent className="space-y-4 pt-5">
              {connector.key === "sharepoint" ? (
                <Button
                  type="button"
                  variant="outline"
                  className="w-full justify-center"
                  onClick={() => void handleConnectMicrosoft()}
                  disabled={isConnectingMicrosoft}
                >
                  {isConnectingMicrosoft ? "Redirecting..." : "Connect Microsoft"}
                </Button>
              ) : null}
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
