"use client";

import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

type CallRow = {
  id: string;
  caller: string;
  outcome: "Answered" | "Missed" | "Voicemail";
  nextAction: string;
  followUpTaskCreated: boolean;
};

const initialCalls: CallRow[] = [
  {
    id: "call-1",
    caller: "Prospect Family Contact",
    outcome: "Answered",
    nextAction: "Send intake checklist",
    followUpTaskCreated: true,
  },
  {
    id: "call-2",
    caller: "Referral Office",
    outcome: "Missed",
    nextAction: "Return call before noon",
    followUpTaskCreated: false,
  },
  {
    id: "call-3",
    caller: "Client Coordinator",
    outcome: "Voicemail",
    nextAction: "Second outreach tomorrow",
    followUpTaskCreated: true,
  },
];

export default function CallsReceptionPage() {
  const [calls, setCalls] = useState<CallRow[]>(initialCalls);

  function createFollowUpTask(id: string) {
    setCalls((current) =>
      current.map((row) =>
        row.id === id ? { ...row, followUpTaskCreated: true } : row,
      ),
    );
  }

  return (
    <div className="flex flex-col gap-8">
      <div className="space-y-3">
        <p className="text-sm font-semibold text-slate-500">Work</p>
        <h1 className="text-[2rem] font-semibold tracking-tight text-slate-900">Calls & Reception</h1>
        <p className="max-w-2xl text-base leading-7 text-slate-600">
          Keep every call visible and tied to a clear next action.
        </p>
      </div>

      <Card className="bg-white shadow-sm">
        <CardHeader className="pb-2">
          <CardTitle className="text-xl text-slate-900">Call log</CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <Table>
            <TableHeader>
              <TableRow className="border-slate-200">
                <TableHead className="text-xs uppercase tracking-[0.18em] text-slate-500">Caller</TableHead>
                <TableHead className="text-xs uppercase tracking-[0.18em] text-slate-500">Outcome</TableHead>
                <TableHead className="text-xs uppercase tracking-[0.18em] text-slate-500">Next action</TableHead>
                <TableHead className="text-xs uppercase tracking-[0.18em] text-slate-500">Follow-up</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {calls.map((row) => (
                <TableRow key={row.id} className="border-slate-200">
                  <TableCell className="text-sm font-semibold text-slate-900">{row.caller}</TableCell>
                  <TableCell>
                    <span className={`rounded-md border px-2 py-0.5 text-xs font-semibold ${row.outcome === "Missed" ? "ui-status-error" : row.outcome === "Voicemail" ? "ui-status-warning" : "ui-status-success"}`}>
                      {row.outcome}
                    </span>
                  </TableCell>
                  <TableCell className="text-sm text-slate-600">{row.nextAction}</TableCell>
                  <TableCell>
                    <Button
                      type="button"
                      variant="outline"
                      className="h-8 rounded-lg"
                      disabled={row.followUpTaskCreated}
                      onClick={() => createFollowUpTask(row.id)}
                    >
                      {row.followUpTaskCreated ? "Task created" : "Create task"}
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
