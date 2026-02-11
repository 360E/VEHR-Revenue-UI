"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const adminAreas = [
  { label: "Organization settings", note: "Manage org-level defaults and policies" },
  { label: "Role permissions", note: "Review access levels and account controls" },
  { label: "Integration controls", note: "Configure external systems and credentials" },
];

export default function AdminCenterPage() {
  return (
    <div className="flex flex-col gap-8">
      <div className="space-y-3">
        <p className="text-sm font-semibold text-slate-500">Admin</p>
        <h1 className="text-[2rem] font-semibold tracking-tight text-slate-900">Admin Center</h1>
        <p className="max-w-2xl text-base leading-7 text-slate-600">
          Centralized controls for organization-wide administration.
        </p>
      </div>

      <Card className="bg-white shadow-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-xl text-slate-900">Administration areas</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 pt-0">
          {adminAreas.map((area) => (
            <div key={area.label} className="rounded-lg bg-slate-50 px-4 py-3">
              <p className="text-sm font-semibold text-slate-900">{area.label}</p>
              <p className="mt-1 text-sm text-slate-600">{area.note}</p>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
