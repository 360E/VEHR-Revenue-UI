"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const punchRows = [
  { staff: "Front Desk A", punchIn: "8:01 AM", punchOut: "-", alert: "Missed punch out", approval: "Pending" },
  { staff: "Admissions B", punchIn: "7:58 AM", punchOut: "4:05 PM", alert: "None", approval: "Approved" },
  { staff: "Compliance C", punchIn: "8:10 AM", punchOut: "-", alert: "Late punch in", approval: "Pending" },
];

export default function TimeAttendancePage() {
  return (
    <div className="flex flex-col gap-8">
      <div className="space-y-3">
        <p className="text-sm font-semibold text-slate-500">Workforce</p>
        <h1 className="text-[2rem] font-semibold tracking-tight text-slate-900">Time & Attendance</h1>
        <p className="max-w-2xl text-base leading-7 text-slate-600">
          Clear punches, missed punch alerts, and supervisor approvals.
        </p>
      </div>

      <Card className="bg-white shadow-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-xl text-slate-900">Today&apos;s punches</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 pt-0">
          {punchRows.map((row) => (
            <div key={row.staff} className="rounded-lg bg-slate-50 px-4 py-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-semibold text-slate-900">{row.staff}</p>
                <span className={`rounded-md border px-2 py-0.5 text-xs font-semibold ${row.approval === "Approved" ? "ui-status-success" : "ui-status-warning"}`}>
                  {row.approval}
                </span>
              </div>
              <div className="mt-1 flex flex-wrap gap-3 text-xs text-slate-500">
                <span>In: {row.punchIn}</span>
                <span>Out: {row.punchOut}</span>
                <span>Alert: {row.alert}</span>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
