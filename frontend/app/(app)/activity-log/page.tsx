"use client";

import { useEffect, useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiFetch } from "@/lib/api";

type SummaryResponse = {
  total_events: number;
  by_action: { key: string; count: number }[];
};

export default function ActivityLogPage() {
  const [summary, setSummary] = useState<SummaryResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadSummary() {
      try {
        const data = await apiFetch<SummaryResponse>("/api/v1/audit/summary?hours=24", { cache: "no-store" });
        if (!isMounted) return;
        setSummary(data);
      } catch (loadError) {
        if (!isMounted) return;
        setError(loadError instanceof Error ? loadError.message : "Unable to load activity.");
      }
    }

    void loadSummary();
    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <div className="flex flex-col gap-8">
      <div className="space-y-3">
        <p className="text-sm font-semibold text-slate-500">Communication</p>
        <h1 className="text-[2rem] font-semibold tracking-tight text-slate-900">Activity Log</h1>
        <p className="max-w-2xl text-base leading-7 text-slate-600">
          Shared operational activity across teams.
        </p>
      </div>

      {error ? <p className="text-sm text-rose-700">{error}</p> : null}

      <Card className="bg-white shadow-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-xl text-slate-900">Latest activity summary</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 pt-0">
          <p className="text-sm text-slate-600">Total events in last 24 hours: {summary?.total_events ?? 0}</p>
          {(summary?.by_action ?? []).slice(0, 10).map((entry) => (
            <div key={entry.key} className="rounded-lg bg-slate-50 px-4 py-2">
              <div className="flex items-center justify-between gap-2">
                <span className="text-sm text-slate-700">{entry.key}</span>
                <span className="text-xs text-slate-500">{entry.count}</span>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
