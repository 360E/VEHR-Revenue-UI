import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

const encounterQueues = [
  {
    label: "Intake Assessments",
    note: "Awaiting clinician assignment",
  },
  {
    label: "Follow-Up Visits",
    note: "Documentation due",
  },
  {
    label: "Care Plan Reviews",
    note: "Pending sign-off",
  },
];

export default function EncountersPage() {
  return (
    <div className="flex flex-col gap-6">
      <div className="space-y-2">
        <p className="text-[11px] font-semibold uppercase tracking-[0.32em] text-slate-400">
          Encounters
        </p>
        <h1 className="text-3xl font-semibold tracking-tight text-slate-900">
          Encounter Queue
        </h1>
        <p className="text-sm text-slate-500">
          Visit timelines, documentation workflow, and clinical status tracking.
        </p>
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.3fr_1fr]">
        <Card className="border-slate-200/70 shadow-sm">
          <CardHeader className="border-b border-slate-200/70 bg-slate-50/70">
            <CardTitle className="text-base text-slate-900">
              Visit Timeline
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-5">
            <div className="space-y-3">
              {["Morning rounds", "Midday check-ins", "Evening handoff"].map(
                (slot) => (
                  <div
                    key={slot}
                    className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50/60 px-4 py-3 text-sm text-slate-600"
                  >
                    <span>{slot}</span>
                    <span className="text-xs text-slate-400">Scheduled</span>
                  </div>
                )
              )}
            </div>
          </CardContent>
        </Card>

        <Card className="border-slate-200/70 shadow-sm">
          <CardHeader className="border-b border-slate-200/70 bg-slate-50/70">
            <CardTitle className="text-base text-slate-900">
              Documentation Queue
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-5">
            <div className="space-y-3 text-sm text-slate-600">
              {encounterQueues.map((item) => (
                <div
                  key={item.label}
                  className="rounded-xl border border-slate-200 bg-white px-4 py-3"
                >
                  <div className="font-medium text-slate-800">{item.label}</div>
                  <div className="text-xs text-slate-500">{item.note}</div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
