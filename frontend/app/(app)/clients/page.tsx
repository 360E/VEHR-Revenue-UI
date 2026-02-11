"use client";

import { useEffect, useMemo, useState } from "react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { apiFetch } from "@/lib/api";

type ClientRecord = {
  id: string;
  first_name: string;
  last_name: string;
};

type ClientStage = "Lead" | "Intake" | "Active" | "Discharged";

const stageOrder: ClientStage[] = ["Lead", "Intake", "Active", "Discharged"];

function stageForIndex(index: number): ClientStage {
  if (index % 4 === 0) return "Lead";
  if (index % 4 === 1) return "Intake";
  if (index % 4 === 2) return "Active";
  return "Discharged";
}

export default function ClientsPage() {
  const [clients, setClients] = useState<ClientRecord[]>([]);
  const [selectedClientId, setSelectedClientId] = useState<string>("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadClients() {
      try {
        setError(null);
        const rows = await apiFetch<ClientRecord[]>("/api/v1/patients", { cache: "no-store" });
        if (!isMounted) return;
        setClients(rows);
        if (rows[0]) {
          setSelectedClientId(rows[0].id);
        }
      } catch (loadError) {
        if (!isMounted) return;
        setError(loadError instanceof Error ? loadError.message : "Unable to load clients.");
      }
    }

    void loadClients();
    return () => {
      isMounted = false;
    };
  }, []);

  const selectedClient = useMemo(
    () => clients.find((client) => client.id === selectedClientId) ?? null,
    [clients, selectedClientId],
  );

  const selectedIndex = useMemo(
    () => clients.findIndex((client) => client.id === selectedClientId),
    [clients, selectedClientId],
  );

  const stage: ClientStage = selectedIndex >= 0 ? stageForIndex(selectedIndex) : "Lead";

  const assignedStaff = ["Admissions Coordinator", "Case Manager", "Compliance Reviewer"];
  const openTasks = [
    "Follow up on intake checklist",
    "Confirm preferred contact window",
    "Review unsigned document",
  ];
  const timeline = [
    "Prospect created from referral",
    "Initial outreach completed",
    "Document packet shared",
    "Awaiting next follow-up",
  ];
  const linkedDocuments = ["Intake Packet", "Consent Form", "Insurance Verification"];

  return (
    <div className="flex flex-col gap-8">
      <div className="space-y-3">
        <p className="text-sm font-semibold text-slate-500">People</p>
        <h1 className="text-[2rem] font-semibold tracking-tight text-slate-900">Clients</h1>
        <p className="max-w-2xl text-base leading-7 text-slate-600">Relationship hub for status, ownership, tasks, activity, and documents.</p>
      </div>

      {error ? <p className="text-sm text-rose-700">{error}</p> : null}

      <div className="grid gap-5 xl:grid-cols-[1fr_2fr]">
        <Card className="bg-white shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-xl text-slate-900">Client list</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 pt-0">
            {clients.length === 0 ? (
              <p className="text-sm text-slate-500">No clients available.</p>
            ) : (
              clients.map((client) => (
                <button
                  key={client.id}
                  type="button"
                  onClick={() => setSelectedClientId(client.id)}
                  className={`w-full rounded-lg px-3 py-2 text-left transition-colors ${
                    selectedClientId === client.id ? "bg-blue-50 text-blue-900" : "bg-slate-50 text-slate-800 hover:bg-slate-100"
                  }`}
                >
                  <p className="text-sm font-semibold">{client.last_name}, {client.first_name}</p>
                  <p className="mt-1 text-xs text-slate-500">Client ID: {client.id}</p>
                </button>
              ))
            )}
          </CardContent>
        </Card>

        <Card className="bg-white shadow-sm">
          <CardHeader className="pb-2">
            <CardTitle className="text-xl text-slate-900">Client profile</CardTitle>
          </CardHeader>
          <CardContent className="space-y-5 pt-0">
            {!selectedClient ? (
              <p className="text-sm text-slate-500">Select a client to view details.</p>
            ) : (
              <>
                <div className="rounded-lg bg-slate-50 px-4 py-3">
                  <p className="text-base font-semibold text-slate-900">{selectedClient.first_name} {selectedClient.last_name}</p>
                  <p className="mt-1 text-sm text-slate-600">Current status: <span className="font-semibold text-slate-800">{stage}</span></p>
                </div>

                <div>
                  <p className="text-sm font-semibold text-slate-700">Status progression</p>
                  <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4">
                    {stageOrder.map((item) => (
                      <div
                        key={item}
                        className={`rounded-lg px-3 py-2 text-xs font-semibold ${
                          item === stage ? "bg-blue-50 text-blue-900" : "bg-slate-100 text-slate-600"
                        }`}
                      >
                        {item}
                      </div>
                    ))}
                  </div>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <p className="text-sm font-semibold text-slate-700">Assigned staff</p>
                    {assignedStaff.map((person) => (
                      <div key={person} className="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700">
                        {person}
                      </div>
                    ))}
                  </div>

                  <div className="space-y-2">
                    <p className="text-sm font-semibold text-slate-700">Open tasks</p>
                    {openTasks.map((task) => (
                      <div key={task} className="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700">
                        {task}
                      </div>
                    ))}
                  </div>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <div className="space-y-2">
                    <p className="text-sm font-semibold text-slate-700">Activity timeline</p>
                    {timeline.map((item) => (
                      <div key={item} className="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700">
                        {item}
                      </div>
                    ))}
                  </div>

                  <div className="space-y-2">
                    <p className="text-sm font-semibold text-slate-700">Linked documents</p>
                    {linkedDocuments.map((document) => (
                      <div key={document} className="rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-700">
                        {document}
                      </div>
                    ))}
                  </div>
                </div>
              </>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
