"use client";

import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import MetricCard from "../_components/MetricCard";
import { apiFetch } from "@/lib/api";

type ClientRecord = {
  id: string;
};

type OperationTask = {
  id: string;
  title: string;
  owner: string;
  due: string;
  status: "Due Today" | "Overdue" | "Waiting";
  context: string;
};

type ActivityItem = {
  id: string;
  text: string;
  time: string;
};

const taskList: OperationTask[] = [
  {
    id: "op-task-1",
    title: "Follow up with no-response referral",
    owner: "Admissions",
    due: "Today 10:30 AM",
    status: "Due Today",
    context: "Pipeline",
  },
  {
    id: "op-task-2",
    title: "Confirm intake call time with new client",
    owner: "Reception",
    due: "Today 1:00 PM",
    status: "Due Today",
    context: "Calls & Reception",
  },
  {
    id: "op-task-3",
    title: "Resolve missing consent document",
    owner: "Compliance",
    due: "Yesterday 4:00 PM",
    status: "Overdue",
    context: "Documents",
  },
  {
    id: "op-task-4",
    title: "Await external insurance verification",
    owner: "Client Services",
    due: "Waiting",
    status: "Waiting",
    context: "Client",
  },
];

const recentActivity: ActivityItem[] = [
  { id: "activity-1", text: "Prospect moved to Intake stage", time: "9:18 AM" },
  { id: "activity-2", text: "Follow-up task completed by Reception", time: "8:52 AM" },
  { id: "activity-3", text: "Client document uploaded", time: "Yesterday" },
  { id: "activity-4", text: "Billing exception reviewed", time: "Yesterday" },
];

function statusClass(status: OperationTask["status"]): string {
  if (status === "Overdue") return "ui-status-error";
  if (status === "Waiting") return "ui-status-info";
  return "ui-status-warning";
}

export default function DashboardPage() {
  const [activeClients, setActiveClients] = useState<number>(0);

  useEffect(() => {
    let isMounted = true;

    async function loadClientCount() {
      try {
        const data = await apiFetch<ClientRecord[]>("/api/v1/patients", { cache: "no-store" });
        if (!isMounted) return;
        setActiveClients(data.length);
      } catch {
        if (!isMounted) return;
        setActiveClients(0);
      }
    }

    void loadClientCount();
    return () => {
      isMounted = false;
    };
  }, []);

  const tasksDueToday = useMemo(() => taskList.filter((task) => task.status === "Due Today").length, []);
  const overdueItems = useMemo(() => taskList.filter((task) => task.status === "Overdue").length, []);
  const openReferrals = 14;

  return (
    <div className="flex flex-col gap-8">
      <div className="space-y-3">
        <p className="text-sm font-semibold text-slate-500">Work</p>
        <h1 className="text-[2rem] font-semibold tracking-tight text-slate-900">Operations</h1>
        <p className="max-w-2xl text-base leading-7 text-slate-600">
          Start here to focus on what matters today.
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard label="Tasks due today" value={`${tasksDueToday}`} hint="Needs action" />
        <MetricCard label="Overdue items" value={`${overdueItems}`} hint="Escalate first" />
        <MetricCard label="Active clients" value={`${activeClients}`} hint="Current relationships" />
        <MetricCard label="Open referrals" value={`${openReferrals}`} hint="Pipeline in progress" />
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.7fr_1fr]">
        <Card className="bg-white shadow-sm">
          <CardHeader className="flex flex-row items-center justify-between pb-2">
            <CardTitle className="text-xl text-slate-900">Task list</CardTitle>
            <Button type="button" className="h-9 rounded-lg px-4">View all tasks</Button>
          </CardHeader>
          <CardContent className="space-y-2 pt-0">
            {taskList.map((task) => (
              <div key={task.id} className="rounded-lg bg-slate-50 px-4 py-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-slate-900">{task.title}</p>
                  <span className={`rounded-md border px-2 py-0.5 text-xs font-semibold ${statusClass(task.status)}`}>
                    {task.status}
                  </span>
                </div>
                <div className="mt-1 flex flex-wrap gap-3 text-xs text-slate-500">
                  <span>Owner: {task.owner}</span>
                  <span>Due: {task.due}</span>
                  <span>Context: {task.context}</span>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card className="bg-white shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-xl text-slate-900">Recent activity</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 pt-0">
            {recentActivity.map((item) => (
              <div key={item.id} className="rounded-lg bg-slate-50 px-3 py-2">
                <p className="text-sm text-slate-700">{item.text}</p>
                <p className="mt-1 text-xs text-slate-500">{item.time}</p>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
