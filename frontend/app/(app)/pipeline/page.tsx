"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const pipelineStages = [
  { name: "New referral", count: 18, nextAction: "Initial contact within 24h" },
  { name: "Qualification", count: 10, nextAction: "Confirm eligibility and fit" },
  { name: "Intake scheduled", count: 7, nextAction: "Prep documents and reminders" },
  { name: "Ready for onboarding", count: 4, nextAction: "Assign internal owner" },
];

export default function PipelinePage() {
  return (
    <div className="flex flex-col gap-8">
      <div className="space-y-3">
        <p className="text-sm font-semibold text-slate-500">Work</p>
        <h1 className="text-[2rem] font-semibold tracking-tight text-slate-900">Pipeline</h1>
        <p className="max-w-2xl text-base leading-7 text-slate-600">
          Referral and prospect progression with clear stage ownership.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {pipelineStages.map((stage) => (
          <Card key={stage.name} className="bg-white shadow-sm">
            <CardHeader className="pb-1">
              <CardTitle className="text-sm font-semibold text-slate-700">{stage.name}</CardTitle>
            </CardHeader>
            <CardContent className="pt-0">
              <p className="text-3xl font-semibold text-slate-900">{stage.count}</p>
              <p className="mt-2 text-xs text-slate-500">{stage.nextAction}</p>
            </CardContent>
          </Card>
        ))}
      </div>
    </div>
  );
}
