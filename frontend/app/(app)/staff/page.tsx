"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const staffRows = [
  { name: "Admissions Team", coverage: "Fully staffed", openItems: 4 },
  { name: "Client Services", coverage: "1 role open", openItems: 7 },
  { name: "Compliance", coverage: "Fully staffed", openItems: 3 },
  { name: "Billing", coverage: "Fully staffed", openItems: 2 },
];

export default function StaffPage() {
  return (
    <div className="flex flex-col gap-8">
      <div className="space-y-3">
        <p className="text-sm font-semibold text-slate-500">People</p>
        <h1 className="text-[2rem] font-semibold tracking-tight text-slate-900">Staff</h1>
        <p className="max-w-2xl text-base leading-7 text-slate-600">
          Team coverage and current workload visibility.
        </p>
      </div>

      <Card className="bg-white shadow-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-xl text-slate-900">Team overview</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 pt-0">
          {staffRows.map((row) => (
            <div key={row.name} className="rounded-lg bg-slate-50 px-4 py-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-semibold text-slate-900">{row.name}</p>
                <p className="text-xs text-slate-500">{row.openItems} open items</p>
              </div>
              <p className="mt-1 text-sm text-slate-600">{row.coverage}</p>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
