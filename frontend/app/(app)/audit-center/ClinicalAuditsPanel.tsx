"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { ApiError, apiFetch } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

type QueueItem = {
  id: string;
  source_finding_id?: string | null;
  subject_type: string;
  subject_id: string;
  reason_code: string;
  severity: "info" | "warning" | "high";
  status: "open" | "needs_correction" | "resolved" | "overridden";
  assigned_to_user_id?: string | null;
  due_at?: string | null;
  created_at: string;
  updated_at: string;
};

type ClinicalFinding = {
  id: string;
  run_id: string;
  signal_type: string;
  subject_type: string;
  subject_id: string;
  severity: "info" | "warning" | "high";
  finding_summary: string;
  evidence_references: string[];
  related_entities: Record<string, string | null>;
  suggested_correction?: string | null;
  confidence_score?: number | null;
  created_at: string;
  queue_item?: QueueItem | null;
  correction_checklist: string[];
};

type ReviewAction = {
  id: string;
  queue_item_id: string;
  action_type: string;
  notes?: string | null;
  justification?: string | null;
  created_by_user_id?: string | null;
  created_at: string;
};

type ReviewEvidence = {
  id: string;
  queue_item_id: string;
  document_id: string;
  created_by_user_id?: string | null;
  created_at: string;
};

type QueueDetail = QueueItem & {
  finding?: ClinicalFinding | null;
  actions: ReviewAction[];
  evidence_links: ReviewEvidence[];
};

const severityOptions = ["all", "high", "warning", "info"] as const;
const signalOptions = [
  "all",
  "clinical_completeness",
  "plan_alignment",
  "internal_consistency",
] as const;
const statusOptions = ["all", "open", "needs_correction", "resolved", "overridden"] as const;

function severityVariant(severity: string) {
  if (severity === "high") return "destructive" as const;
  if (severity === "warning") return "secondary" as const;
  return "outline" as const;
}

function queueStatusVariant(status: string) {
  if (status === "resolved") return "default" as const;
  if (status === "overridden") return "destructive" as const;
  if (status === "needs_correction") return "secondary" as const;
  return "outline" as const;
}

function toErrorMessage(err: unknown) {
  if (err instanceof ApiError) {
    return `API ${err.status}: ${err.message}`;
  }
  return err instanceof Error ? err.message : "Unexpected request failure";
}

export default function ClinicalAuditsPanel() {
  const [findings, setFindings] = useState<ClinicalFinding[]>([]);
  const [queueDetail, setQueueDetail] = useState<QueueDetail | null>(null);
  const [selectedFindingId, setSelectedFindingId] = useState<string | null>(null);
  const [severityFilter, setSeverityFilter] = useState<(typeof severityOptions)[number]>("all");
  const [signalFilter, setSignalFilter] = useState<(typeof signalOptions)[number]>("all");
  const [statusFilter, setStatusFilter] = useState<(typeof statusOptions)[number]>("all");
  const [assignedToMe, setAssignedToMe] = useState(false);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [nextStatus, setNextStatus] = useState<"open" | "needs_correction" | "resolved" | "overridden">("needs_correction");
  const [justification, setJustification] = useState("");
  const [note, setNote] = useState("");
  const [evidenceDocumentId, setEvidenceDocumentId] = useState("");

  const selectedFinding = useMemo(
    () => findings.find((finding) => finding.id === selectedFindingId) ?? null,
    [findings, selectedFindingId],
  );

  const loadFindings = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      params.set("limit", "200");
      if (severityFilter !== "all") params.set("severity", severityFilter);
      if (signalFilter !== "all") params.set("signal_type", signalFilter);
      if (statusFilter !== "all") params.set("status", statusFilter);

      const findingData = await apiFetch<ClinicalFinding[]>(
        `/api/v1/clinical-audit/findings?${params.toString()}`,
        { cache: "no-store" },
      );

      let filteredFindings = findingData;
      if (assignedToMe) {
        const queueItems = await apiFetch<QueueItem[]>(
          "/api/v1/clinical-audit/queue?assigned_to_me=true&limit=200",
          { cache: "no-store" },
        );
        const assignedIds = new Set(queueItems.map((item) => item.id));
        filteredFindings = findingData.filter(
          (finding) => finding.queue_item?.id && assignedIds.has(finding.queue_item.id),
        );
      }

      setFindings(filteredFindings);
      if (!filteredFindings.length) {
        setSelectedFindingId(null);
        setQueueDetail(null);
      } else if (!selectedFindingId || !filteredFindings.find((f) => f.id === selectedFindingId)) {
        setSelectedFindingId(filteredFindings[0].id);
      }
    } catch (err) {
      setError(toErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [assignedToMe, selectedFindingId, severityFilter, signalFilter, statusFilter]);

  const loadQueueDetail = useCallback(async (queueItemId: string | null | undefined) => {
    if (!queueItemId) {
      setQueueDetail(null);
      return;
    }
    try {
      const detail = await apiFetch<QueueDetail>(`/api/v1/clinical-audit/queue/${queueItemId}`, {
        cache: "no-store",
      });
      setQueueDetail(detail);
    } catch (err) {
      setQueueDetail(null);
      setError(toErrorMessage(err));
    }
  }, []);

  useEffect(() => {
    loadFindings();
  }, [loadFindings]);

  useEffect(() => {
    const finding = findings.find((item) => item.id === selectedFindingId);
    if (!finding?.queue_item?.id) {
      setQueueDetail(null);
      return;
    }
    loadQueueDetail(finding.queue_item.id);
  }, [findings, selectedFindingId, loadQueueDetail]);

  async function refreshAndKeepSelection() {
    await loadFindings();
    const currentQueueId = findings.find((f) => f.id === selectedFindingId)?.queue_item?.id;
    if (currentQueueId) {
      await loadQueueDetail(currentQueueId);
    }
  }

  async function handleCreateQueueFromFinding() {
    if (!selectedFinding) return;
    setBusy(true);
    setStatusMessage(null);
    setError(null);
    try {
      await apiFetch<QueueItem>(`/api/v1/clinical-audit/findings/${selectedFinding.id}/queue`, {
        method: "POST",
      });
      setStatusMessage("Queue item created from finding.");
      await refreshAndKeepSelection();
    } catch (err) {
      setError(toErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleAssignToMe() {
    if (!selectedFinding?.queue_item?.id) return;
    setBusy(true);
    setStatusMessage(null);
    setError(null);
    try {
      await apiFetch<QueueItem>(
        `/api/v1/clinical-audit/queue/${selectedFinding.queue_item.id}/assign-to-me`,
        { method: "POST" },
      );
      setStatusMessage("Queue item assigned to you.");
      await refreshAndKeepSelection();
    } catch (err) {
      setError(toErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleStatusUpdate() {
    if (!selectedFinding?.queue_item?.id) return;
    setBusy(true);
    setStatusMessage(null);
    setError(null);
    try {
      await apiFetch<QueueItem>(`/api/v1/clinical-audit/queue/${selectedFinding.queue_item.id}/status`, {
        method: "POST",
        body: JSON.stringify({
          status: nextStatus,
          justification: justification || null,
        }),
      });
      setStatusMessage(`Queue status updated to ${nextStatus}.`);
      await refreshAndKeepSelection();
    } catch (err) {
      setError(toErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleAddNote() {
    if (!selectedFinding?.queue_item?.id || !note.trim()) return;
    setBusy(true);
    setStatusMessage(null);
    setError(null);
    try {
      await apiFetch<ReviewAction>(`/api/v1/clinical-audit/queue/${selectedFinding.queue_item.id}/actions`, {
        method: "POST",
        body: JSON.stringify({
          action_type: "note",
          notes: note.trim(),
        }),
      });
      setNote("");
      setStatusMessage("Review note added.");
      await refreshAndKeepSelection();
    } catch (err) {
      setError(toErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  async function handleAttachEvidence() {
    if (!selectedFinding?.queue_item?.id || !evidenceDocumentId.trim()) return;
    setBusy(true);
    setStatusMessage(null);
    setError(null);
    try {
      await apiFetch<ReviewEvidence>(
        `/api/v1/clinical-audit/queue/${selectedFinding.queue_item.id}/evidence`,
        {
          method: "POST",
          body: JSON.stringify({ document_id: evidenceDocumentId.trim() }),
        },
      );
      setEvidenceDocumentId("");
      setStatusMessage("Evidence document linked.");
      await refreshAndKeepSelection();
    } catch (err) {
      setError(toErrorMessage(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="border-slate-200/70 shadow-sm">
      <CardHeader className="border-b border-slate-200/70 bg-slate-50/70">
        <CardTitle className="text-base text-slate-900">Clinical Audits</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4 pt-5">
        <div className="grid gap-3 lg:grid-cols-5">
          <label className="space-y-1 text-xs text-slate-500">
            Severity
            <select
              className="h-9 w-full rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700"
              value={severityFilter}
              onChange={(event) => setSeverityFilter(event.target.value as (typeof severityOptions)[number])}
            >
              {severityOptions.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>

          <label className="space-y-1 text-xs text-slate-500">
            Signal
            <select
              className="h-9 w-full rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700"
              value={signalFilter}
              onChange={(event) => setSignalFilter(event.target.value as (typeof signalOptions)[number])}
            >
              {signalOptions.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>

          <label className="space-y-1 text-xs text-slate-500">
            Queue Status
            <select
              className="h-9 w-full rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700"
              value={statusFilter}
              onChange={(event) => setStatusFilter(event.target.value as (typeof statusOptions)[number])}
            >
              {statusOptions.map((option) => (
                <option key={option} value={option}>
                  {option}
                </option>
              ))}
            </select>
          </label>

          <label className="flex items-end gap-2 rounded-md border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600">
            <input
              type="checkbox"
              checked={assignedToMe}
              onChange={(event) => setAssignedToMe(event.target.checked)}
            />
            Assigned to me
          </label>

          <div className="flex items-end">
            <Button
              type="button"
              variant="outline"
              className="w-full"
              onClick={loadFindings}
              disabled={loading}
            >
              Refresh
            </Button>
          </div>
        </div>

        {error ? (
          <div className="rounded-md border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
            {error}
          </div>
        ) : null}
        {statusMessage ? (
          <div className="rounded-md border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm text-emerald-700">
            {statusMessage}
          </div>
        ) : null}

        <div className="grid gap-4 lg:grid-cols-[1.05fr_1fr]">
          <div className="space-y-3">
            <div className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">
              Findings Queue
            </div>
            <div className="max-h-[540px] space-y-2 overflow-auto pr-1">
              {!findings.length ? (
                <div className="rounded-xl border border-slate-200 bg-white px-4 py-6 text-sm text-slate-500">
                  {loading ? "Loading clinical audit findings..." : "No findings for current filters."}
                </div>
              ) : (
                findings.map((finding) => {
                  const isActive = selectedFindingId === finding.id;
                  return (
                    <button
                      key={finding.id}
                      type="button"
                      onClick={() => setSelectedFindingId(finding.id)}
                      className={`w-full rounded-xl border px-4 py-3 text-left transition ${
                        isActive
                          ? "border-cyan-300 bg-cyan-50/70"
                          : "border-slate-200 bg-white hover:border-slate-300"
                      }`}
                    >
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="text-sm font-semibold text-slate-900">{finding.signal_type}</div>
                        <div className="flex items-center gap-2">
                          <Badge variant={severityVariant(finding.severity)}>{finding.severity}</Badge>
                          {finding.queue_item ? (
                            <Badge variant={queueStatusVariant(finding.queue_item.status)}>
                              {finding.queue_item.status}
                            </Badge>
                          ) : (
                            <Badge variant="outline">no queue</Badge>
                          )}
                        </div>
                      </div>
                      <p className="mt-2 line-clamp-2 text-sm text-slate-600">{finding.finding_summary}</p>
                      <p className="mt-2 text-xs text-slate-500">
                        {new Date(finding.created_at).toLocaleString()} | subject: {finding.subject_type}
                      </p>
                    </button>
                  );
                })
              )}
            </div>
          </div>

          <div className="space-y-3">
            <div className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">
              Finding Detail
            </div>
            {!selectedFinding ? (
              <div className="rounded-xl border border-slate-200 bg-white px-4 py-6 text-sm text-slate-500">
                Select a finding to review details.
              </div>
            ) : (
              <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
                <div className="flex flex-wrap items-center gap-2">
                  <Badge variant={severityVariant(selectedFinding.severity)}>
                    {selectedFinding.severity}
                  </Badge>
                  <Badge variant="outline">{selectedFinding.signal_type}</Badge>
                  {selectedFinding.queue_item ? (
                    <Badge variant={queueStatusVariant(selectedFinding.queue_item.status)}>
                      {selectedFinding.queue_item.status}
                    </Badge>
                  ) : null}
                </div>

                <p className="text-sm text-slate-700">{selectedFinding.finding_summary}</p>
                <p className="text-xs text-slate-500">
                  Subject: {selectedFinding.subject_type} | {selectedFinding.subject_id}
                </p>

                <div>
                  <div className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">
                    Evidence References
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    {selectedFinding.evidence_references.map((reference) => (
                      <Badge key={reference} variant="outline">
                        {reference}
                      </Badge>
                    ))}
                  </div>
                </div>

                <div>
                  <div className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">
                    Correction Plan Checklist
                  </div>
                  <ul className="mt-2 list-disc space-y-1 pl-5 text-sm text-slate-700">
                    {selectedFinding.correction_checklist.map((item) => (
                      <li key={item}>{item}</li>
                    ))}
                  </ul>
                </div>

                {!selectedFinding.queue_item ? (
                  <Button type="button" onClick={handleCreateQueueFromFinding} disabled={busy}>
                    Create Queue Item
                  </Button>
                ) : (
                  <div className="space-y-3 rounded-lg border border-slate-200 bg-slate-50/60 p-3">
                    <div className="grid gap-2 sm:grid-cols-2">
                      <Button
                        type="button"
                        variant="outline"
                        onClick={handleAssignToMe}
                        disabled={busy}
                      >
                        Assign To Me
                      </Button>
                      <div className="flex gap-2">
                        <select
                          value={nextStatus}
                          onChange={(event) =>
                            setNextStatus(
                              event.target.value as "open" | "needs_correction" | "resolved" | "overridden",
                            )
                          }
                          className="h-9 flex-1 rounded-md border border-slate-200 bg-white px-2 text-sm text-slate-700"
                        >
                          {statusOptions
                            .filter((option) => option !== "all")
                            .map((option) => (
                              <option key={option} value={option}>
                                {option}
                              </option>
                            ))}
                        </select>
                        <Button type="button" onClick={handleStatusUpdate} disabled={busy}>
                          Set
                        </Button>
                      </div>
                    </div>

                    <Input
                      value={justification}
                      onChange={(event) => setJustification(event.target.value)}
                      placeholder="Override justification (required for overridden status)"
                    />

                    <div className="grid gap-2 sm:grid-cols-2">
                      <div className="space-y-2">
                        <textarea
                          className="min-h-[90px] w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700"
                          placeholder="Add review note"
                          value={note}
                          onChange={(event) => setNote(event.target.value)}
                        />
                        <Button type="button" variant="outline" onClick={handleAddNote} disabled={busy || !note.trim()}>
                          Add Note
                        </Button>
                      </div>
                      <div className="space-y-2">
                        <Input
                          placeholder="Evidence document ID"
                          value={evidenceDocumentId}
                          onChange={(event) => setEvidenceDocumentId(event.target.value)}
                        />
                        <Button
                          type="button"
                          variant="outline"
                          onClick={handleAttachEvidence}
                          disabled={busy || !evidenceDocumentId.trim()}
                        >
                          Attach Evidence
                        </Button>
                      </div>
                    </div>
                  </div>
                )}

                {queueDetail ? (
                  <div className="space-y-2 rounded-lg border border-slate-200 bg-slate-50/50 p-3">
                    <div className="text-xs font-semibold uppercase tracking-[0.24em] text-slate-400">
                      Queue Activity
                    </div>
                    <div className="space-y-2 text-xs text-slate-600">
                      {queueDetail.actions.slice(0, 4).map((action) => (
                        <div key={action.id} className="rounded-md border border-slate-200 bg-white px-2 py-1.5">
                          <div className="font-semibold text-slate-700">{action.action_type}</div>
                          {action.notes ? <div>{action.notes}</div> : null}
                          {action.justification ? <div>Justification: {action.justification}</div> : null}
                          <div className="text-[11px] text-slate-500">
                            {new Date(action.created_at).toLocaleString()}
                          </div>
                        </div>
                      ))}
                      {queueDetail.evidence_links.slice(0, 4).map((evidence) => (
                        <div key={evidence.id} className="rounded-md border border-slate-200 bg-white px-2 py-1.5">
                          Evidence Document: {evidence.document_id}
                        </div>
                      ))}
                      {!queueDetail.actions.length && !queueDetail.evidence_links.length ? (
                        <div>No queue actions or evidence linked yet.</div>
                      ) : null}
                    </div>
                  </div>
                ) : null}
              </div>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
