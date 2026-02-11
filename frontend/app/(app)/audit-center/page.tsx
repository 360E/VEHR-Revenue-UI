"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import MetricCard from "../_components/MetricCard";
import { apiFetch } from "@/lib/api";

type SummaryResponse = {
  window_hours: number;
  total_events: number;
};

type Anomaly = {
  kind: string;
  severity: string;
  description: string;
  sample_time: string;
};

function severityClass(severity: string): string {
  if (severity === "high") return "ui-status-error";
  if (severity === "medium") return "ui-status-warning";
  return "ui-status-info";
}

export default function AuditCenterPage() {
  const [summary, setSummary] = useState<SummaryResponse | null>(null);
  const [findings, setFindings] = useState<Anomaly[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadData() {
      try {
        setError(null);
        const [summaryRes, anomalyRes] = await Promise.all([
          apiFetch<SummaryResponse>("/api/v1/audit/summary?hours=72", { cache: "no-store" }),
          apiFetch<Anomaly[]>("/api/v1/audit/anomalies?hours=72&limit=8", { cache: "no-store" }),
        ]);
        if (!isMounted) return;
        setSummary(summaryRes);
        setFindings(anomalyRes);
      } catch (loadError) {
        if (!isMounted) return;
        setError(loadError instanceof Error ? loadError.message : "Unable to load audit data.");
      }
    }

    void loadData();
    return () => {
      isMounted = false;
    };
  }, []);

  const highRisk = findings.filter((item) => item.severity === "high").length;

  return (
    <div className="flex flex-col gap-8">
      <div className="space-y-3">
        <p className="text-sm font-semibold text-slate-500">Oversight</p>
        <h1 className="text-[2rem] font-semibold tracking-tight text-slate-900">Audit Center</h1>
        <p className="max-w-2xl text-base leading-7 text-slate-600">
          Status-first audit view with clear risk and direct follow-up actions.
        </p>
      </div>

      {error ? <p className="text-sm text-rose-700">{error}</p> : null}

      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard label="Audit window" value={`${summary?.window_hours ?? 72}h`} hint="Current review period" />
        <MetricCard label="Tracked events" value={`${summary?.total_events ?? 0}`} hint="Observed activity" />
        <MetricCard label="High-risk findings" value={`${highRisk}`} hint="Requires immediate review" />
      </div>

      <Card className="bg-white shadow-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-xl text-slate-900">Findings queue</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 pt-0">
          {findings.length === 0 ? (
            <p className="text-sm text-slate-500">No active findings in this period.</p>
          ) : (
            findings.map((finding) => (
              <div key={`${finding.kind}-${finding.sample_time}`} className="rounded-lg bg-slate-50 px-4 py-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-slate-900">{finding.kind}</p>
                  <span className={`rounded-md border px-2 py-0.5 text-xs font-semibold ${severityClass(finding.severity)}`}>
                    {finding.severity}
                  </span>
                </div>
                <p className="mt-1 text-sm text-slate-600">{finding.description}</p>
                <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
                  <p className="text-xs text-slate-500">Detected: {new Date(finding.sample_time).toLocaleString()}</p>
                  <Button type="button" variant="outline" className="h-8 rounded-lg">
                    Create follow-up task
                  </Button>
                </div>
              </div>
            ))
          )}
        </CardContent>
      </Card>
    </div>
  );
}
