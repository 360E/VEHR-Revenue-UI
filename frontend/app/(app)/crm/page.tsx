import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import MetricCard from "../_components/MetricCard";

const pipeline = [
  { stage: "Inbound Referral", count: 14, trend: "+3 this week" },
  { stage: "Intake Scheduled", count: 9, trend: "+1 this week" },
  { stage: "Pending Authorization", count: 6, trend: "-2 this week" },
  { stage: "Admitted", count: 5, trend: "stable" },
];

const taskQueue = [
  { task: "Follow up with provider network", owner: "Partnerships", priority: "high" },
  { task: "Verify insurance authorizations", owner: "Admissions", priority: "medium" },
  { task: "Send welcome packets", owner: "Care Coordination", priority: "low" },
  { task: "Review open referral notes", owner: "Clinical Intake", priority: "medium" },
];

function priorityVariant(priority: string) {
  if (priority === "high") {
    return "destructive" as const;
  }
  if (priority === "medium") {
    return "secondary" as const;
  }
  return "outline" as const;
}

export default function CrmPage() {
  return (
    <div className="flex flex-col gap-6">
      <div className="space-y-2">
        <p className="text-[11px] font-semibold uppercase tracking-[0.32em] text-slate-400">
          Operations
        </p>
        <h1 className="text-3xl font-semibold tracking-tight text-slate-900">CRM Workspace</h1>
        <p className="text-sm text-slate-500">
          Referral pipeline, relationship tracking, and intake operations in one queue.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard label="Open Leads" value="28" hint="Active referral opportunities" />
        <MetricCard label="Conversion" value="42%" hint="Lead to admission (30 days)" />
        <MetricCard label="Tasks Due" value="11" hint="Priority follow-ups this week" />
      </div>

      <div className="grid gap-4 lg:grid-cols-[1.2fr_1fr]">
        <Card className="border-slate-200/70 shadow-sm">
          <CardHeader className="border-b border-slate-200/70 bg-slate-50/70">
            <CardTitle className="text-base text-slate-900">Pipeline Overview</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 pt-5">
            {pipeline.map((stage) => (
              <div key={stage.stage} className="rounded-xl border border-slate-200 bg-white px-4 py-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="text-sm font-semibold text-slate-800">{stage.stage}</div>
                  <div className="text-sm font-mono text-slate-700">{stage.count}</div>
                </div>
                <p className="mt-1 text-xs text-slate-500">{stage.trend}</p>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card className="border-slate-200/70 shadow-sm">
          <CardHeader className="border-b border-slate-200/70 bg-slate-50/70">
            <CardTitle className="text-base text-slate-900">Follow-Up Queue</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 pt-5">
            {taskQueue.map((item) => (
              <div key={item.task} className="rounded-xl border border-slate-200 bg-white px-4 py-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="text-sm font-semibold text-slate-800">{item.task}</div>
                  <Badge variant={priorityVariant(item.priority)}>{item.priority}</Badge>
                </div>
                <p className="mt-1 text-xs text-slate-500">Owner: {item.owner}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
