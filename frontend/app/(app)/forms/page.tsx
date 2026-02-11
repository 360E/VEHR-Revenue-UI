"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const forms = [
  { id: "form-1", name: "Client Intake Checklist", owner: "Admissions", status: "Active" },
  { id: "form-2", name: "Follow-up Contact Record", owner: "Client Services", status: "Active" },
  { id: "form-3", name: "Billing Escalation Form", owner: "Billing", status: "Draft" },
];

export default function FormsPage() {
  return (
    <div className="flex flex-col gap-8">
      <div className="space-y-3">
        <p className="text-sm font-semibold text-slate-500">Documents</p>
        <h1 className="text-[2rem] font-semibold tracking-tight text-slate-900">Forms</h1>
        <p className="max-w-2xl text-base leading-7 text-slate-600">
          Operational forms for intake, communication, and coordination.
        </p>
      </div>

      <Card className="bg-white shadow-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-xl text-slate-900">Form library</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 pt-0">
          {forms.map((form) => (
            <div key={form.id} className="rounded-lg bg-slate-50 px-4 py-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-semibold text-slate-900">{form.name}</p>
                <span className={`rounded-md border px-2 py-0.5 text-xs font-semibold ${form.status === "Active" ? "ui-status-success" : "ui-status-warning"}`}>
                  {form.status}
                </span>
              </div>
              <p className="mt-1 text-xs text-slate-500">Owner: {form.owner}</p>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
