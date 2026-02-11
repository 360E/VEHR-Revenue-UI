"use client";

import { useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type TaskView = "my" | "team" | "overdue" | "external";

type TaskRow = {
  id: string;
  title: string;
  owner: string;
  due: string;
  status: "Open" | "Completed";
  bucket: "my" | "team" | "overdue" | "external";
  context: string;
};

const initialTasks: TaskRow[] = [
  {
    id: "task-1",
    title: "Call referral source and confirm intake details",
    owner: "You",
    due: "Today 10:30 AM",
    status: "Open",
    bucket: "my",
    context: "Pipeline",
  },
  {
    id: "task-2",
    title: "Complete missed call follow-up",
    owner: "You",
    due: "Today 1:00 PM",
    status: "Open",
    bucket: "my",
    context: "Calls",
  },
  {
    id: "task-3",
    title: "Approve intake checklist updates",
    owner: "Team",
    due: "Tomorrow",
    status: "Open",
    bucket: "team",
    context: "Clients",
  },
  {
    id: "task-4",
    title: "Resolve overdue billing exception",
    owner: "Team",
    due: "Overdue",
    status: "Open",
    bucket: "overdue",
    context: "Billing",
  },
  {
    id: "task-5",
    title: "Waiting for payer authorization",
    owner: "External",
    due: "Waiting",
    status: "Open",
    bucket: "external",
    context: "Client",
  },
];

const views: { key: TaskView; label: string }[] = [
  { key: "my", label: "My Tasks" },
  { key: "team", label: "Team Tasks" },
  { key: "overdue", label: "Overdue" },
  { key: "external", label: "Waiting on External" },
];

export default function TasksPage() {
  const [activeView, setActiveView] = useState<TaskView>("my");
  const [tasks, setTasks] = useState<TaskRow[]>(initialTasks);
  const [selected, setSelected] = useState<Record<string, boolean>>({});

  const visibleTasks = useMemo(
    () => tasks.filter((task) => task.bucket === activeView),
    [activeView, tasks],
  );

  function toggleSelected(id: string) {
    setSelected((current) => ({ ...current, [id]: !current[id] }));
  }

  function markComplete(id: string) {
    setTasks((current) => current.map((task) => (task.id === id ? { ...task, status: "Completed" } : task)));
  }

  function bulkComplete() {
    const selectedIds = Object.entries(selected)
      .filter(([, value]) => value)
      .map(([id]) => id);
    if (selectedIds.length === 0) return;

    setTasks((current) =>
      current.map((task) =>
        selectedIds.includes(task.id) ? { ...task, status: "Completed" } : task,
      ),
    );
    setSelected({});
  }

  return (
    <div className="flex flex-col gap-8">
      <div className="space-y-3">
        <p className="text-sm font-semibold text-slate-500">Work</p>
        <h1 className="text-[2rem] font-semibold tracking-tight text-slate-900">Tasks</h1>
        <p className="max-w-2xl text-base leading-7 text-slate-600">Clear ownership, clear due dates, clear next actions.</p>
      </div>

      <Card className="bg-white shadow-sm">
        <CardHeader className="flex flex-col gap-3 pb-2">
          <CardTitle className="text-xl text-slate-900">Task views</CardTitle>
          <div className="flex flex-wrap gap-2">
            {views.map((view) => (
              <Button
                key={view.key}
                type="button"
                variant={activeView === view.key ? "default" : "outline"}
                className="h-9 rounded-lg"
                onClick={() => setActiveView(view.key)}
              >
                {view.label}
              </Button>
            ))}
          </div>
        </CardHeader>
        <CardContent className="space-y-3 pt-0">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm text-slate-500">{visibleTasks.length} tasks in this view</p>
            <Button type="button" variant="outline" className="h-9 rounded-lg" onClick={bulkComplete}>
              Mark selected complete
            </Button>
          </div>

          {visibleTasks.map((task) => (
            <div key={task.id} className="flex flex-wrap items-start gap-3 rounded-lg bg-slate-50 px-4 py-3">
              <input
                type="checkbox"
                aria-label={`Select task ${task.title}`}
                checked={Boolean(selected[task.id])}
                onChange={() => toggleSelected(task.id)}
                className="mt-1 h-4 w-4 rounded border-slate-300"
              />
              <div className="min-w-[220px] flex-1">
                <p className="text-sm font-semibold text-slate-900">{task.title}</p>
                <div className="mt-1 flex flex-wrap gap-3 text-xs text-slate-500">
                  <span>Owner: {task.owner}</span>
                  <span>Due: {task.due}</span>
                  <span>Context: {task.context}</span>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <span className={`rounded-md border px-2 py-0.5 text-xs font-semibold ${task.status === "Completed" ? "ui-status-success" : "ui-status-warning"}`}>
                  {task.status}
                </span>
                <Button
                  type="button"
                  variant="outline"
                  className="h-8 rounded-lg"
                  onClick={() => markComplete(task.id)}
                  disabled={task.status === "Completed"}
                >
                  Complete
                </Button>
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}
