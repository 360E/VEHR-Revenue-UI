"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const complianceItems = [
  { item: "Policy acknowledgements", status: "On track", risk: "Low" },
  { item: "Documentation completion", status: "Review needed", risk: "Medium" },
  { item: "Audit follow-up closure", status: "Attention required", risk: "High" },
];

export default function CompliancePage() {
  return (
    <div className="flex flex-col gap-8">
      <div className="space-y-3">
        <p className="text-sm font-semibold text-slate-500">Oversight</p>
        <h1 className="text-[2rem] font-semibold tracking-tight text-slate-900">Compliance</h1>
        <p className="max-w-2xl text-base leading-7 text-slate-600">
          Status-first oversight with clear risk indicators.
        </p>
      </div>

      <Card className="bg-white shadow-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-xl text-slate-900">Risk status</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 pt-0">
          {complianceItems.map((row) => (
            <div key={row.item} className="rounded-lg bg-slate-50 px-4 py-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-semibold text-slate-900">{row.item}</p>
                <span className={`rounded-md border px-2 py-0.5 text-xs font-semibold ${row.risk === "High" ? "ui-status-error" : row.risk === "Medium" ? "ui-status-warning" : "ui-status-success"}`}>
                  {row.risk}
                </span>
              </div>
              <p className="mt-1 text-sm text-slate-600">{row.status}</p>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
