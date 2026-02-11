"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const payrollRows = [
  { cycle: "Current pay period", status: "Processing", exportStatus: "Pending", auditTrail: "4 updates" },
  { cycle: "Previous pay period", status: "Closed", exportStatus: "Exported", auditTrail: "No exceptions" },
];

export default function PayrollPage() {
  return (
    <div className="flex flex-col gap-8">
      <div className="space-y-3">
        <p className="text-sm font-semibold text-slate-500">Workforce</p>
        <h1 className="text-[2rem] font-semibold tracking-tight text-slate-900">Payroll</h1>
        <p className="max-w-2xl text-base leading-7 text-slate-600">
          Read-only payroll summaries with export status and audit trace.
        </p>
      </div>

      <Card className="bg-white shadow-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-xl text-slate-900">Payroll status</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 pt-0">
          {payrollRows.map((row) => (
            <div key={row.cycle} className="rounded-lg bg-slate-50 px-4 py-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-semibold text-slate-900">{row.cycle}</p>
                <span className={`rounded-md border px-2 py-0.5 text-xs font-semibold ${row.status === "Closed" ? "ui-status-success" : "ui-status-warning"}`}>
                  {row.status}
                </span>
              </div>
              <div className="mt-1 flex flex-wrap gap-3 text-xs text-slate-500">
                <span>Export: {row.exportStatus}</span>
                <span>Audit trail: {row.auditTrail}</span>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
