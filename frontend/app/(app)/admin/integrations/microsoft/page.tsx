"use client";

import { useMemo } from "react";
import { useSearchParams } from "next/navigation";
import { CheckCircle2, ExternalLink, Link2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const DEFAULT_API_BASE_URL = "https://api.360-encompass.com";

function resolveApiBaseUrl() {
  const configured = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  return (configured && configured.length > 0 ? configured : DEFAULT_API_BASE_URL).replace(/\/$/, "");
}

export default function MicrosoftIntegrationPage() {
  const searchParams = useSearchParams();
  const status = searchParams.get("status");
  const reason = searchParams.get("reason");

  const connectUrl = useMemo(() => {
    return `${resolveApiBaseUrl()}/api/v1/integrations/microsoft/connect`;
  }, []);

  return (
    <div className="flex flex-col gap-6">
      <div className="space-y-2">
        <p className="text-[11px] font-semibold uppercase tracking-[0.32em] text-slate-400">
          Integration Hub
        </p>
        <h1 className="text-3xl font-semibold tracking-tight text-slate-900">Microsoft Graph</h1>
        <p className="text-sm text-slate-500">
          Connect delegated Microsoft access for your organization.
        </p>
      </div>

      {status === "connected" ? (
        <Card className="border-emerald-200 bg-emerald-50/70">
          <CardContent className="flex items-center gap-2 pt-6 text-sm font-medium text-emerald-800">
            <CheckCircle2 className="h-4 w-4" />
            Microsoft account connected successfully.
          </CardContent>
        </Card>
      ) : null}

      {status === "error" ? (
        <Card className="border-amber-200 bg-amber-50/70">
          <CardContent className="pt-6 text-sm text-amber-800">
            Microsoft connection could not be completed.
            {reason ? ` Reason: ${reason.replaceAll("_", " ")}.` : ""}
          </CardContent>
        </Card>
      ) : null}

      <Card className="border-slate-200/70 shadow-sm">
        <CardHeader className="border-b border-slate-200/70 bg-slate-50/70">
          <CardTitle className="text-base text-slate-900">Delegated OAuth</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4 pt-5">
          <p className="text-sm text-slate-600">
            Use delegated OAuth to authorize Microsoft Graph access for your active organization.
          </p>
          <Button asChild>
            <a href={connectUrl} target="_blank" rel="noopener noreferrer">
              Connect Microsoft
              <ExternalLink className="h-4 w-4" />
            </a>
          </Button>
          <p className="text-xs text-slate-500">
            Endpoint: <span className="font-mono">{connectUrl}</span>
          </p>
          <div className="flex items-start gap-2 rounded-lg border border-slate-200 bg-slate-50 p-3 text-xs text-slate-600">
            <Link2 className="mt-0.5 h-4 w-4 shrink-0 text-slate-500" />
            <span>
              This opens Microsoft consent in a new tab and returns to this page with a status
              indicator.
            </span>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
