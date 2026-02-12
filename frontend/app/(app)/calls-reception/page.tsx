"use client";

import { useEffect, useMemo, useState } from "react";

import { getBrowserAccessToken } from "@/lib/auth";
import { ApiError, apiFetch, buildUrl } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

type PresenceItem = {
  user_id: string;
  full_name?: string | null;
  email: string;
  role: string;
  extension_id?: string | null;
  status: "available" | "on_call" | "offline" | string;
  updated_at?: string | null;
  source: string;
};

type CallRow = {
  call_id: string;
  state: string;
  disposition?: string | null;
  from_number?: string | null;
  to_number?: string | null;
  direction?: string | null;
  extension_id?: string | null;
  started_at?: string | null;
  ended_at?: string | null;
  last_event_at: string;
  overlay_status: "NEW" | "MISSED" | "CALLED_BACK" | "RESOLVED";
  assigned_to_user_id?: string | null;
  notes?: string | null;
};

type SnapshotResponse = {
  presence: PresenceItem[];
  active_calls: CallRow[];
  call_log: CallRow[];
  subscription_status: string;
  last_webhook_received_at?: string | null;
};

type DispositionResponse = {
  call_id: string;
  status: "NEW" | "MISSED" | "CALLED_BACK" | "RESOLVED";
  assigned_to_user_id?: string | null;
  notes?: string | null;
  updated_at: string;
};

type CallEventPayload = {
  call_id: string;
  state: string;
  disposition?: string | null;
  from_number?: string | null;
  to_number?: string | null;
  direction?: string | null;
  extension_id?: string | null;
  started_at?: string | null;
  ended_at?: string | null;
  overlay_status?: "NEW" | "MISSED" | "CALLED_BACK" | "RESOLVED";
  assigned_to_user_id?: string | null;
  notes?: string | null;
};

type PresenceEventPayload = {
  extension_id?: string | null;
  status?: string | null;
};

type DispositionEventPayload = {
  call_id: string;
  status: "NEW" | "MISSED" | "CALLED_BACK" | "RESOLVED";
  assigned_to_user_id?: string | null;
  notes?: string | null;
};

const WORKFLOW_OPTIONS = ["NEW", "MISSED", "CALLED_BACK", "RESOLVED"] as const;

function toMessage(error: unknown, fallback: string): string {
  if (error instanceof ApiError || error instanceof Error) {
    return error.message || fallback;
  }
  return fallback;
}

function formatDateTime(value: string | null | undefined): string {
  if (!value) return "n/a";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "n/a";
  return parsed.toLocaleString();
}

function callStatusBadge(state: string): string {
  const normalized = state.trim().toLowerCase();
  if (normalized === "missed") return "ui-status-error";
  if (normalized === "answered" || normalized === "connected") return "ui-status-success";
  if (normalized === "ringing") return "ui-status-warning";
  return "ui-status-info";
}

function presenceDot(status: string): string {
  if (status === "on_call") return "bg-rose-500";
  if (status === "available") return "bg-emerald-500";
  return "bg-slate-400";
}

function upsertCall(calls: CallRow[], incoming: Partial<CallRow> & { call_id: string }): CallRow[] {
  const existing = calls.find((item) => item.call_id === incoming.call_id);
  const merged: CallRow = {
    call_id: incoming.call_id,
    state: incoming.state || existing?.state || "unknown",
    disposition: incoming.disposition ?? existing?.disposition ?? null,
    from_number: incoming.from_number ?? existing?.from_number ?? null,
    to_number: incoming.to_number ?? existing?.to_number ?? null,
    direction: incoming.direction ?? existing?.direction ?? null,
    extension_id: incoming.extension_id ?? existing?.extension_id ?? null,
    started_at: incoming.started_at ?? existing?.started_at ?? null,
    ended_at: incoming.ended_at ?? existing?.ended_at ?? null,
    last_event_at: incoming.last_event_at || new Date().toISOString(),
    overlay_status: incoming.overlay_status ?? existing?.overlay_status ?? "NEW",
    assigned_to_user_id: incoming.assigned_to_user_id ?? existing?.assigned_to_user_id ?? null,
    notes: incoming.notes ?? existing?.notes ?? null,
  };

  const withoutCurrent = calls.filter((item) => item.call_id !== incoming.call_id);
  return [merged, ...withoutCurrent].sort(
    (a, b) => new Date(b.last_event_at).getTime() - new Date(a.last_event_at).getTime(),
  );
}

export default function CallsReceptionPage() {
  const [presence, setPresence] = useState<PresenceItem[]>([]);
  const [callLog, setCallLog] = useState<CallRow[]>([]);
  const [selectedCallId, setSelectedCallId] = useState<string | null>(null);
  const [workflowStatus, setWorkflowStatus] =
    useState<(typeof WORKFLOW_OPTIONS)[number]>("NEW");
  const [workflowNote, setWorkflowNote] = useState("");
  const [subscriptionStatus, setSubscriptionStatus] = useState("MISSING");
  const [streamStatus, setStreamStatus] = useState("connecting");
  const [isLoading, setIsLoading] = useState(true);
  const [isSavingDisposition, setIsSavingDisposition] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const activeCalls = useMemo(
    () => callLog.filter((row) => ["ringing", "answered", "connected", "in_progress", "on_call"].includes(row.state)),
    [callLog],
  );

  const selectedCall = useMemo(
    () => callLog.find((row) => row.call_id === selectedCallId) ?? null,
    [callLog, selectedCallId],
  );

  useEffect(() => {
    if (!selectedCall) {
      setWorkflowStatus("NEW");
      setWorkflowNote("");
      return;
    }
    setWorkflowStatus(selectedCall.overlay_status);
    setWorkflowNote(selectedCall.notes || "");
  }, [selectedCall]);

  useEffect(() => {
    let mounted = true;
    async function loadSnapshot() {
      setIsLoading(true);
      setError(null);
      try {
        const snapshot = await apiFetch<SnapshotResponse>("/api/v1/call-center/snapshot", {
          cache: "no-store",
        });
        if (!mounted) return;
        setPresence(snapshot.presence);
        setCallLog(snapshot.call_log);
        setSubscriptionStatus(snapshot.subscription_status);
        if (snapshot.call_log[0]) {
          setSelectedCallId((current) => current || snapshot.call_log[0].call_id);
        }
      } catch (loadError) {
        if (!mounted) return;
        setError(toMessage(loadError, "Unable to load call center snapshot."));
      } finally {
        if (mounted) setIsLoading(false);
      }
    }
    void loadSnapshot();
    return () => {
      mounted = false;
    };
  }, []);

  useEffect(() => {
    const token = getBrowserAccessToken();
    if (!token) {
      setStreamStatus("offline");
      return;
    }
    const streamUrl = `${buildUrl("/api/v1/call-center/stream")}?access_token=${encodeURIComponent(token)}`;
    const source = new EventSource(streamUrl, { withCredentials: true });
    setStreamStatus("connecting");

    source.addEventListener("open", () => {
      setStreamStatus("connected");
    });

    source.addEventListener("presence", (event) => {
      const payload = JSON.parse((event as MessageEvent).data) as PresenceEventPayload;
      setPresence((current) =>
        current.map((item) =>
          item.extension_id && payload.extension_id && item.extension_id === payload.extension_id
            ? { ...item, status: payload.status || item.status, source: "ringcentral_presence" }
            : item,
        ),
      );
    });

    source.addEventListener("call", (event) => {
      const payload = JSON.parse((event as MessageEvent).data) as CallEventPayload;
      setCallLog((current) =>
        upsertCall(current, {
          call_id: payload.call_id,
          state: payload.state,
          disposition: payload.disposition,
          from_number: payload.from_number,
          to_number: payload.to_number,
          direction: payload.direction,
          extension_id: payload.extension_id,
          started_at: payload.started_at,
          ended_at: payload.ended_at,
          overlay_status: payload.overlay_status,
          assigned_to_user_id: payload.assigned_to_user_id,
          notes: payload.notes,
          last_event_at: new Date().toISOString(),
        }),
      );
      setSelectedCallId((current) => current || payload.call_id);
    });

    source.addEventListener("disposition", (event) => {
      const payload = JSON.parse((event as MessageEvent).data) as DispositionEventPayload;
      setCallLog((current) =>
        upsertCall(current, {
          call_id: payload.call_id,
          overlay_status: payload.status,
          assigned_to_user_id: payload.assigned_to_user_id,
          notes: payload.notes,
          last_event_at: new Date().toISOString(),
        }),
      );
    });

    source.addEventListener("snapshot", (event) => {
      const payload = JSON.parse((event as MessageEvent).data) as SnapshotResponse;
      setPresence(payload.presence);
      setCallLog(payload.call_log);
      setSubscriptionStatus(payload.subscription_status);
    });

    source.onerror = () => {
      setStreamStatus("reconnecting");
    };

    return () => {
      source.close();
      setStreamStatus("offline");
    };
  }, []);

  async function handleSaveDisposition() {
    if (!selectedCall) return;
    setIsSavingDisposition(true);
    setError(null);
    setMessage(null);
    try {
      const response = await apiFetch<DispositionResponse>(
        `/api/v1/call-center/calls/${encodeURIComponent(selectedCall.call_id)}/disposition`,
        {
          method: "POST",
          body: JSON.stringify({
            status: workflowStatus,
            notes: workflowNote || null,
            assigned_to_user_id: selectedCall.assigned_to_user_id || null,
          }),
        },
      );
      setCallLog((current) =>
        upsertCall(current, {
          call_id: response.call_id,
          overlay_status: response.status,
          assigned_to_user_id: response.assigned_to_user_id,
          notes: response.notes,
          last_event_at: response.updated_at,
        }),
      );
      setMessage("Disposition saved.");
    } catch (saveError) {
      setError(toMessage(saveError, "Unable to save disposition."));
    } finally {
      setIsSavingDisposition(false);
    }
  }

  return (
    <div className="flex flex-col gap-8">
      <div className="space-y-3">
        <p className="text-sm font-semibold text-slate-500">Work</p>
        <h1 className="text-[2rem] font-semibold tracking-tight text-slate-900">Calls & Reception</h1>
        <p className="max-w-3xl text-base leading-7 text-slate-600">
          Real-time call center powered by RingCentral webhooks and SSE.
        </p>
        <p className="text-xs text-slate-500">
          Stream: {streamStatus} - Subscription: {subscriptionStatus}
        </p>
      </div>

      {error ? <p className="text-sm text-rose-700">{error}</p> : null}
      {message ? <p className="text-sm text-slate-700">{message}</p> : null}
      {isLoading ? <p className="text-sm text-slate-600">Loading call center...</p> : null}

      {!isLoading ? (
        <div className="grid gap-5 xl:grid-cols-[320px_1.4fr_1fr]">
          <Card className="bg-white shadow-sm">
            <CardHeader className="pb-2">
              <CardTitle className="text-xl text-slate-900">Staff Presence</CardTitle>
            </CardHeader>
            <CardContent className="space-y-2 pt-0">
              {presence.length === 0 ? (
                <p className="text-sm text-slate-500">No presence data yet.</p>
              ) : (
                presence.map((item) => (
                  <div key={item.user_id} className="rounded-lg bg-slate-50 px-3 py-2">
                    <div className="flex items-center gap-2">
                      <span className={`h-2.5 w-2.5 rounded-full ${presenceDot(item.status)}`} />
                      <p className="truncate text-sm font-semibold text-slate-900">
                        {item.full_name || item.email}
                      </p>
                    </div>
                    <p className="mt-1 text-xs text-slate-500">
                      {item.status} - {item.role}
                    </p>
                  </div>
                ))
              )}
            </CardContent>
          </Card>

          <Card className="bg-white shadow-sm">
            <CardHeader className="gap-2 pb-2">
              <CardTitle className="text-xl text-slate-900">Live Calls</CardTitle>
              <p className="text-xs text-slate-500">{activeCalls.length} active - {callLog.length} recent</p>
            </CardHeader>
            <CardContent className="space-y-2 pt-0">
              {callLog.length === 0 ? (
                <p className="text-sm text-slate-500">No calls yet.</p>
              ) : (
                callLog.map((row) => (
                  <button
                    key={row.call_id}
                    type="button"
                    className={`w-full rounded-lg border px-3 py-2 text-left transition-colors ${
                      selectedCallId === row.call_id
                        ? "border-sky-300 bg-sky-50"
                        : "border-slate-200 bg-slate-50 hover:bg-slate-100"
                    }`}
                    onClick={() => setSelectedCallId(row.call_id)}
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-sm font-semibold text-slate-900">
                        {row.from_number || "Unknown"}{" -> "}{row.to_number || "Unknown"}
                      </p>
                      <span className={`rounded-md border px-2 py-0.5 text-xs font-semibold ${callStatusBadge(row.state)}`}>
                        {row.state}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-slate-500">
                      {formatDateTime(row.started_at || row.last_event_at)}
                    </p>
                    <p className="mt-1 text-xs text-slate-500">Overlay: {row.overlay_status}</p>
                  </button>
                ))
              )}
            </CardContent>
          </Card>

          <Card className="bg-white shadow-sm">
            <CardHeader className="pb-2">
              <CardTitle className="text-xl text-slate-900">Workflow Overlay</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3 pt-0">
              {!selectedCall ? (
                <p className="text-sm text-slate-500">Select a call to update workflow.</p>
              ) : (
                <>
                  <div className="rounded-lg bg-slate-50 px-3 py-2 text-sm">
                    <p className="font-semibold text-slate-900">
                      {selectedCall.from_number || "Unknown"}{" -> "}{selectedCall.to_number || "Unknown"}
                    </p>
                    <p className="mt-1 text-xs text-slate-500">Call state: {selectedCall.state}</p>
                    <p className="text-xs text-slate-500">Started: {formatDateTime(selectedCall.started_at)}</p>
                  </div>

                  <div className="space-y-2">
                    <label className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500" htmlFor="workflow_status">
                      Disposition
                    </label>
                    <select
                      id="workflow_status"
                      className="h-9 w-full rounded-md border border-slate-200 bg-white px-3 text-sm"
                      value={workflowStatus}
                      onChange={(event) => setWorkflowStatus(event.target.value as (typeof WORKFLOW_OPTIONS)[number])}
                    >
                      {WORKFLOW_OPTIONS.map((value) => (
                        <option key={value} value={value}>
                          {value}
                        </option>
                      ))}
                    </select>
                  </div>

                  <div className="space-y-2">
                    <label className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500" htmlFor="workflow_note">
                      Notes
                    </label>
                    <textarea
                      id="workflow_note"
                      className="min-h-24 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm"
                      value={workflowNote}
                      onChange={(event) => setWorkflowNote(event.target.value)}
                    />
                  </div>

                  <Button
                    type="button"
                    className="h-9 rounded-lg px-3"
                    onClick={() => void handleSaveDisposition()}
                    disabled={isSavingDisposition}
                  >
                    {isSavingDisposition ? "Saving..." : "Save disposition"}
                  </Button>
                </>
              )}
            </CardContent>
          </Card>
        </div>
      ) : null}
    </div>
  );
}
