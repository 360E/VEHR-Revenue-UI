"use client";

import { Clipboard, Loader2, Send, X } from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  acknowledgeAnalyticsAlert,
  fetchAnalyticsAiAudit,
  fetchAnalyticsAlerts,
  queryAnalyticsAi,
  resolveAnalyticsAlert,
  type AnalyticsAlertRead,
  type AnalyticsAiAuditLogRead,
  type AnalyticsAiEvidenceMetric,
  type AnalyticsAiFilters,
} from "@/lib/analytics/api";

type EiPanelProps = {
  open: boolean;
  onClose: () => void;
  reportKey: string;
  reportTitle: string;
  initialAlert?: AnalyticsAlertRead | null;
  defaultFilters?: AnalyticsAiFilters;
};

type EiMessage =
  | {
    id: string;
    role: "user";
    content: string;
    createdAt: number;
  }
  | {
    id: string;
    role: "ei";
    status: "loading" | "done" | "error";
    answer: string;
    createdAt: number;
    metricsUsed: string[];
    filtersApplied: Record<string, unknown> | null;
    nextStepTasks: string[];
    evidence: AnalyticsAiEvidenceMetric[];
  };

type AlertStatusFilter = "open" | "acknowledged" | "resolved";
type EiTab = "ask" | "audit";

function formatDateYmd(date: Date): string {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
}

function startOfWeekMonday(date: Date): Date {
  const d = new Date(date.getFullYear(), date.getMonth(), date.getDate());
  const dayOfWeek = d.getDay();
  const daysSinceMonday = (dayOfWeek + 6) % 7;
  d.setDate(d.getDate() - daysSinceMonday);
  return d;
}

function isRateMetric(metricKey: string): boolean {
  return metricKey.toLowerCase().includes("rate");
}

function formatMetricValue(metricKey: string, value: number | null): string {
  if (value === null || Number.isNaN(value)) {
    return "-";
  }
  if (isRateMetric(metricKey)) {
    const ratio = value <= 1 ? value * 100 : value;
    return `${ratio.toFixed(1)}%`;
  }
  return value.toLocaleString(undefined, { maximumFractionDigits: 2 });
}

function severityBadgeClass(severity: string): string {
  const normalized = (severity ?? "").toLowerCase();
  switch (normalized) {
    case "critical":
      return "border-rose-200 bg-rose-50 text-rose-700";
    case "high":
      return "border-orange-200 bg-orange-50 text-orange-700";
    case "medium":
      return "border-amber-200 bg-amber-50 text-amber-700";
    case "low":
      return "border-sky-200 bg-sky-50 text-sky-700";
    case "info":
    default:
      return "border-slate-200 bg-slate-50 text-slate-700";
  }
}

function formatDeltaPct(value?: number | null): string {
  if (typeof value !== "number" || Number.isNaN(value)) return "";
  const sign = value >= 0 ? "+" : "-";
  return `${sign}${Math.abs(value).toFixed(1)}%`;
}

function formatAuditTime(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
}

function extractDateRange(filters: Record<string, unknown> | null | undefined): string | null {
  if (!filters) return null;
  const start = typeof filters.start === "string" ? filters.start : null;
  const end = typeof filters.end === "string" ? filters.end : null;
  if (!start && !end) return null;
  if (start && end) return `${start} to ${end}`;
  return start ?? end;
}

function renderFilters(filters: Record<string, unknown> | null | undefined): string {
  if (!filters) return "none";
  const range = extractDateRange(filters);
  const facility = typeof filters.facility_id === "string" ? filters.facility_id : null;
  const program = typeof filters.program_id === "string" ? filters.program_id : null;
  const provider = typeof filters.provider_id === "string" ? filters.provider_id : null;
  const payer = typeof filters.payer_id === "string" ? filters.payer_id : null;

  const parts = [
    range ? `date=${range}` : null,
    facility ? `facility=${facility}` : null,
    program ? `program=${program}` : null,
    provider ? `provider=${provider}` : null,
    payer ? `payer=${payer}` : null,
  ].filter(Boolean);

  return parts.length > 0 ? parts.join("  ") : "none";
}

export default function EiPanel({ open, onClose, reportKey, reportTitle, initialAlert, defaultFilters }: EiPanelProps) {
  const [alerts, setAlerts] = useState<AnalyticsAlertRead[]>([]);
  const [alertsError, setAlertsError] = useState<string | null>(null);
  const [alertsStatus, setAlertsStatus] = useState<AlertStatusFilter>("open");
  const [alertsWindow, setAlertsWindow] = useState<"all" | 7 | 30 | 90>("all");
  const [alertsLoading, setAlertsLoading] = useState(false);
  const [alertActionBusyId, setAlertActionBusyId] = useState<string | null>(null);
  const [tab, setTab] = useState<EiTab>("ask");

  const [auditRows, setAuditRows] = useState<AnalyticsAiAuditLogRead[]>([]);
  const [auditLoading, setAuditLoading] = useState(false);
  const [auditError, setAuditError] = useState<string | null>(null);
  const [copiedAuditId, setCopiedAuditId] = useState<string | null>(null);
  const [auditRefreshNonce, setAuditRefreshNonce] = useState(0);
  const [messages, setMessages] = useState<EiMessage[]>([]);
  const [draft, setDraft] = useState("");
  const [isSending, setIsSending] = useState(false);

  const chatRef = useRef<HTMLDivElement | null>(null);
  const lastInjectedAlertRef = useRef<string | null>(null);

  const filters = useMemo<AnalyticsAiFilters>(() => {
    if (defaultFilters?.start && defaultFilters?.end) return defaultFilters;

    const today = new Date();
    const weekStart = startOfWeekMonday(today);
    return {
      start: formatDateYmd(weekStart),
      end: formatDateYmd(today),
    };
  }, [defaultFilters]);

  function injectAlertContext(alert: AnalyticsAlertRead) {
    const now = Date.now();
    const metricKey = alert.metric_key ?? "";
    const contentLines = [
      `Alert: ${alert.title}`,
      "",
      alert.summary,
      "",
      alert.recommended_actions?.length
        ? `Recommended actions:\n- ${alert.recommended_actions.join("\n- ")}`
        : "Recommended actions: none",
    ];

    const eiMessage: EiMessage = {
      id: `ei-alert-${now}`,
      role: "ei",
      status: "done",
      answer: contentLines.join("\n"),
      createdAt: now,
      metricsUsed: metricKey ? [metricKey] : [],
      filtersApplied: {
        start: alert.current_range_start,
        end: alert.current_range_end,
      },
      nextStepTasks: alert.recommended_actions ?? [],
      evidence: [],
    };

    setMessages((current) => [...current, eiMessage]);
  }

  const visibleAlerts = useMemo(() => {
    if (alertsWindow === "all") return alerts;
    return alerts.filter((row) => row.baseline_window_days === alertsWindow);
  }, [alerts, alertsWindow]);

  useEffect(() => {
    if (!open) {
      lastInjectedAlertRef.current = null;
      setCopiedAuditId(null);
      return;
    }
    setTab("ask");
  }, [open]);

  useEffect(() => {
    if (!open) return;
    let isMounted = true;

    async function loadAlerts() {
      setAlertsLoading(true);
      setAlertsError(null);
      try {
        const rows = await fetchAnalyticsAlerts({ status: alertsStatus, limit: 20 });
        if (!isMounted) return;
        setAlerts(rows);
      } catch (error) {
        if (!isMounted) return;
        setAlertsError(error instanceof Error ? error.message : "Unable to load alerts.");
        setAlerts([]);
      } finally {
        if (isMounted) setAlertsLoading(false);
      }
    }

    void loadAlerts();
    return () => {
      isMounted = false;
    };
  }, [alertsStatus, open]);

  useEffect(() => {
    if (!open) return;
    if (!initialAlert) return;
    if (lastInjectedAlertRef.current === initialAlert.id) return;
    lastInjectedAlertRef.current = initialAlert.id;
    injectAlertContext(initialAlert);
  }, [initialAlert, open]);

  useEffect(() => {
    if (!open) return;
    if (tab !== "ask") return;
    const node = chatRef.current;
    if (!node) return;
    node.scrollTop = node.scrollHeight;
  }, [messages, open, tab]);

  useEffect(() => {
    if (!open) return;
    if (tab !== "audit") return;
    let isMounted = true;

    async function loadAudit() {
      setAuditLoading(true);
      setAuditError(null);
      try {
        const rows = await fetchAnalyticsAiAudit({ report_key: reportKey, limit: 25 });
        if (!isMounted) return;
        setAuditRows(rows);
      } catch (error) {
        if (!isMounted) return;
        setAuditError(error instanceof Error ? error.message : "Unable to load audit logs.");
        setAuditRows([]);
      } finally {
        if (isMounted) setAuditLoading(false);
      }
    }

    void loadAudit();
    return () => {
      isMounted = false;
    };
  }, [auditRefreshNonce, open, reportKey, tab]);

  async function sendMessage(text: string) {
    const trimmed = text.trim();
    if (!trimmed || isSending) return;

    const now = Date.now();
    const userMessage: EiMessage = {
      id: `user-${now}`,
      role: "user",
      content: trimmed,
      createdAt: now,
    };

    const placeholder: EiMessage = {
      id: `ei-${now}`,
      role: "ei",
      status: "loading",
      answer: "Analyzing metrics...",
      createdAt: now + 1,
      metricsUsed: [],
      filtersApplied: null,
      nextStepTasks: [],
      evidence: [],
    };

    setMessages((current) => [...current, userMessage, placeholder]);
    setDraft("");
    setIsSending(true);

    try {
      const payload = await queryAnalyticsAi(trimmed, { report_key: reportKey, filters });

      const response: EiMessage = {
        id: placeholder.id,
        role: "ei",
        status: "done",
        answer: payload.answer,
        createdAt: placeholder.createdAt,
        metricsUsed: payload.metrics_used ?? [],
        filtersApplied: payload.filters_applied ?? null,
        nextStepTasks: payload.next_step_tasks ?? [],
        evidence: payload.evidence ?? [],
      };

      setMessages((current) =>
        current.map((msg) => (msg.id === placeholder.id ? response : msg)),
      );
    } catch (error) {
      console.error("EI panel query failed", error);
      const response: EiMessage = {
        id: placeholder.id,
        role: "ei",
        status: "error",
        answer: error instanceof Error ? error.message : "EI request failed.",
        createdAt: placeholder.createdAt,
        metricsUsed: [],
        filtersApplied: null,
        nextStepTasks: [],
        evidence: [],
      };

      setMessages((current) =>
        current.map((msg) => (msg.id === placeholder.id ? response : msg)),
      );
    } finally {
      setIsSending(false);
    }
  }

  async function copyAuditRow(row: AnalyticsAiAuditLogRead) {
    setCopiedAuditId(null);
    const payload = {
      id: row.id,
      created_at: row.created_at,
      report_key: row.report_key,
      intent: row.intent,
      prompt: row.user_prompt,
      rationale: row.rationale,
      metrics_used: row.metrics_used,
      filters_applied: row.filters_applied,
      query_requests: row.query_requests,
      query_responses_summary: row.query_responses_summary,
    };
    const text = JSON.stringify(payload, null, 2);
    try {
      if (!navigator.clipboard?.writeText) {
        throw new Error("Clipboard API unavailable");
      }
      await navigator.clipboard.writeText(text);
      setCopiedAuditId(row.id);
      window.setTimeout(() => {
        setCopiedAuditId((current) => (current === row.id ? null : current));
      }, 1200);
    } catch (error) {
      console.error("Unable to copy audit details", error);
    }
  }

  return (
    <>
      <button
        type="button"
        aria-label="Close EI panel"
        onClick={onClose}
        className={`fixed inset-0 z-40 bg-slate-900/30 backdrop-blur-sm transition-opacity ${open ? "opacity-100" : "pointer-events-none opacity-0"}`}
      />

      <aside
        className={`fixed right-0 top-0 z-50 flex h-full w-[92vw] max-w-[460px] flex-col border-l border-slate-200 bg-white shadow-[0_20px_60px_-30px_rgba(15,23,42,0.5)] transition-transform duration-300 ${open ? "translate-x-0" : "translate-x-full"}`}
        role="dialog"
        aria-modal="true"
        aria-label="EI Insights panel"
      >
        <div className="flex items-start justify-between gap-3 border-b border-slate-200 px-5 py-4">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">EI Insights</p>
            <p className="mt-1 text-base font-semibold text-slate-900">{reportTitle}</p>
            <p className="mt-1 text-xs text-slate-500">Report key: {reportKey}</p>
          </div>
          <Button type="button" variant="ghost" size="icon" onClick={onClose} aria-label="Close panel">
            <X className="h-5 w-5" />
          </Button>
        </div>

        <div ref={chatRef} className="flex-1 overflow-y-auto px-5 py-4">
          <section className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
            <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Alerts</p>
                <p className="mt-1 text-sm text-slate-600">Recent KPI anomalies detected from baseline comparisons.</p>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <select
                  value={alertsStatus}
                  onChange={(event) => setAlertsStatus(event.target.value as AlertStatusFilter)}
                  className="h-9 rounded-lg border border-slate-200 bg-white px-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-200"
                  aria-label="Alert status filter"
                >
                  <option value="open">Open</option>
                  <option value="acknowledged">Acknowledged</option>
                  <option value="resolved">Resolved</option>
                </select>

                <select
                  value={alertsWindow}
                  onChange={(event) => {
                    const value = event.target.value;
                    if (value === "all") {
                      setAlertsWindow("all");
                    } else {
                      setAlertsWindow(Number(value) as 7 | 30 | 90);
                    }
                  }}
                  className="h-9 rounded-lg border border-slate-200 bg-white px-2 text-sm text-slate-700 focus:outline-none focus:ring-2 focus:ring-indigo-200"
                  aria-label="Baseline window filter"
                >
                  <option value="all">All windows</option>
                  <option value="7">7 days</option>
                  <option value="30">30 days</option>
                  <option value="90">90 days</option>
                </select>
              </div>
            </div>

            {alertsError ? (
              <div className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                Alerts unavailable: {alertsError}
              </div>
            ) : null}

            {alertsLoading ? (
              <div className="mt-3 space-y-2">
                {Array.from({ length: 3 }).map((_, index) => (
                  <div key={`alerts-loading-${index}`} className="h-14 animate-pulse rounded-lg bg-slate-100" />
                ))}
              </div>
            ) : null}

            {!alertsLoading && !alertsError ? (
              visibleAlerts.length > 0 ? (
                <div className="mt-3 space-y-2">
                  {visibleAlerts.map((alert) => {
                    const deltaLabel = formatDeltaPct(alert.delta_pct);
                    const actionsDisabled = alertActionBusyId === alert.id;
                    const canAck = alert.status === "open";
                    const canResolve = alert.status !== "resolved";

                    async function updateAlert(action: "ack" | "resolve") {
                      if (actionsDisabled) return;
                      setAlertActionBusyId(alert.id);
                      setAlertsError(null);
                      try {
                        const updated = action === "ack"
                          ? await acknowledgeAnalyticsAlert(alert.id)
                          : await resolveAnalyticsAlert(alert.id);

                        setAlerts((current) => {
                          // If we are filtering by status, remove rows that no longer match.
                          if (alertsStatus && updated.status !== alertsStatus) {
                            return current.filter((row) => row.id !== alert.id);
                          }
                          return current.map((row) => (row.id === alert.id ? updated : row));
                        });
                      } catch (err) {
                        console.error("Alert update failed", err);
                        setAlertsError(err instanceof Error ? err.message : "Unable to update alert.");
                      } finally {
                        setAlertActionBusyId((current) => (current === alert.id ? null : current));
                      }
                    }

                    return (
                      <div key={alert.id} className="rounded-lg border border-slate-200 bg-white px-3 py-2">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className={`inline-flex rounded-full border px-2 py-0.5 text-xs font-semibold ${severityBadgeClass(alert.severity)}`}>
                              {alert.severity}
                            </span>
                            {alert.metric_key ? (
                              <span className="text-xs font-medium text-slate-500">{alert.metric_key}</span>
                            ) : null}
                            <span className="text-xs text-slate-500">{alert.baseline_window_days}d</span>
                            {deltaLabel ? (
                              <span className="text-xs font-semibold text-slate-700">{deltaLabel}</span>
                            ) : null}
                          </div>

                          <div className="flex items-center gap-2">
                            <Button
                              type="button"
                              variant="secondary"
                              size="sm"
                              onClick={() => injectAlertContext(alert)}
                            >
                              Open
                            </Button>
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              disabled={!canAck || actionsDisabled}
                              onClick={() => void updateAlert("ack")}
                            >
                              Acknowledge
                            </Button>
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              disabled={!canResolve || actionsDisabled}
                              onClick={() => void updateAlert("resolve")}
                            >
                              Resolve
                            </Button>
                          </div>
                        </div>

                        <p className="mt-2 text-sm font-semibold text-slate-900">{alert.title}</p>
                        <p className="mt-1 line-clamp-2 text-sm text-slate-600">{alert.summary}</p>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="mt-3 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
                  No alerts for the selected filters.
                </div>
              )
            ) : null}
          </section>

          <Tabs value={tab} onValueChange={(value) => setTab(value as EiTab)} className="mt-4">
            <TabsList className="grid w-full grid-cols-2">
              <TabsTrigger value="ask">Ask</TabsTrigger>
              <TabsTrigger value="audit">Audit</TabsTrigger>
            </TabsList>

            <TabsContent value="ask" className="mt-4">
              {messages.length === 0 ? (
                <div className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm text-slate-600">
                  Ask a question about this report. EI will use governed metrics from the analytics layer.
                </div>
              ) : null}

              <div className="mt-4 space-y-4">
                {messages.map((msg) => {
                  const isUser = msg.role === "user";
                  if (isUser) {
                    return (
                      <div key={msg.id} className="flex justify-end">
                        <div className="max-w-[85%] rounded-2xl bg-slate-900 px-4 py-3 text-sm text-white">
                          {msg.content}
                        </div>
                      </div>
                    );
                  }

                  const statusTone = msg.status === "error"
                    ? "border-rose-200 bg-rose-50 text-rose-800"
                    : "border-slate-200 bg-white text-slate-800";

                  return (
                    <div key={msg.id} className="flex justify-start">
                      <div className={`max-w-[92%] rounded-2xl border px-4 py-3 text-sm shadow-sm ${statusTone}`}>
                        <div className="whitespace-pre-line">{msg.status === "loading" ? "Analyzing metrics..." : msg.answer}</div>
                        {msg.status === "loading" ? (
                          <div className="mt-2 inline-flex items-center gap-2 text-xs text-slate-500">
                            <Loader2 className="h-4 w-4 animate-spin" />
                            Working...
                          </div>
                        ) : null}

                        {msg.status === "done" ? (
                          <div className="mt-4 space-y-3">
                            <div>
                              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Evidence</p>
                              {msg.evidence.length > 0 ? (
                                <div className="mt-2 overflow-hidden rounded-lg border border-slate-200">
                                  <div className="grid grid-cols-12 gap-2 bg-slate-50 px-3 py-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">
                                    <div className="col-span-6">Metric</div>
                                    <div className="col-span-3 text-right">Current</div>
                                    <div className="col-span-3 text-right">Delta</div>
                                  </div>
                                  <div className="divide-y divide-slate-200 bg-white">
                                    {msg.evidence.map((row) => {
                                      const delta = typeof row.delta_pct === "number" ? formatDeltaPct(row.delta_pct) : "";
                                      return (
                                        <div key={`${msg.id}-${row.metric_key}`} className="grid grid-cols-12 gap-2 px-3 py-2 text-xs">
                                          <div className="col-span-6 min-w-0">
                                            <p className="truncate font-semibold text-slate-900">{row.label}</p>
                                            <p className="truncate text-[11px] text-slate-500">{row.metric_key}</p>
                                            {row.error ? (
                                              <p className="mt-1 text-[11px] text-rose-700">{row.error}</p>
                                            ) : null}
                                          </div>
                                          <div className="col-span-3 text-right font-semibold text-slate-900">
                                            {formatMetricValue(row.metric_key, row.current_value ?? null)}
                                          </div>
                                          <div className="col-span-3 text-right font-semibold text-slate-700">
                                            {delta || "-"}
                                          </div>
                                        </div>
                                      );
                                    })}
                                  </div>
                                </div>
                              ) : (
                                <p className="mt-2 text-xs text-slate-600">No evidence metrics were returned.</p>
                              )}
                            </div>

                            <div className="grid gap-3 md:grid-cols-2">
                              <div className="rounded-lg border border-slate-200 bg-white px-3 py-2">
                                <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">Metrics Used</p>
                                <p className="mt-1 text-xs text-slate-700">
                                  {msg.metricsUsed.length > 0 ? msg.metricsUsed.join(", ") : "none"}
                                </p>
                              </div>
                              <div className="rounded-lg border border-slate-200 bg-white px-3 py-2">
                                <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">Filters Applied</p>
                                <p className="mt-1 text-xs text-slate-700">{renderFilters(msg.filtersApplied)}</p>
                              </div>
                            </div>

                            <div className="rounded-lg border border-slate-200 bg-white px-3 py-2">
                              <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-slate-500">Next-Step Tasks</p>
                              {msg.nextStepTasks.length > 0 ? (
                                <ul className="mt-2 list-disc space-y-1 pl-5 text-xs text-slate-700">
                                  {msg.nextStepTasks.map((item) => (
                                    <li key={item}>{item}</li>
                                  ))}
                                </ul>
                              ) : (
                                <p className="mt-2 text-xs text-slate-600">No tasks suggested.</p>
                              )}
                            </div>
                          </div>
                        ) : null}

                        {msg.status === "error" ? (
                          <div className="mt-3">
                            <Button
                              type="button"
                              variant="outline"
                              size="sm"
                              onClick={() => {
                                const lastUser = [...messages].reverse().find((m) => m.role === "user");
                                if (lastUser) {
                                  void sendMessage(lastUser.content);
                                }
                              }}
                            >
                              Retry
                            </Button>
                          </div>
                        ) : null}
                      </div>
                    </div>
                  );
                })}
              </div>
            </TabsContent>

            <TabsContent value="audit" className="mt-4">
              <div className="rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-500">Audit</p>
                    <p className="mt-1 text-sm text-slate-600">
                      Server-side record of EI interactions (metrics selected, filters applied, and query payloads).
                    </p>
                  </div>
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={() => setAuditRefreshNonce((value) => value + 1)}
                  >
                    Refresh
                  </Button>
                </div>

                {auditError ? (
                  <div className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-700">
                    Audit unavailable: {auditError}
                  </div>
                ) : null}

                {auditLoading ? (
                  <div className="mt-4 space-y-2">
                    {Array.from({ length: 3 }).map((_, index) => (
                      <div key={`audit-skel-${index}`} className="h-16 animate-pulse rounded-lg bg-slate-100" />
                    ))}
                  </div>
                ) : null}

                {!auditLoading && !auditError ? (
                  auditRows.length > 0 ? (
                    <div className="mt-4 space-y-3">
                      {auditRows.map((row) => {
                        const range = extractDateRange(row.filters_applied);
                        return (
                          <div key={row.id} className="rounded-xl border border-slate-200 bg-white p-4">
                            <div className="flex items-start justify-between gap-3">
                              <div className="min-w-0">
                                <p className="text-xs text-slate-500">{formatAuditTime(row.created_at)}</p>
                                <p className="mt-1 truncate text-sm font-semibold text-slate-900">{row.user_prompt}</p>
                                <div className="mt-2 flex flex-wrap items-center gap-2 text-xs text-slate-600">
                                  <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5">
                                    intent: {row.intent}
                                  </span>
                                  {range ? (
                                    <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5">
                                      {range}
                                    </span>
                                  ) : null}
                                  {row.metrics_used.length > 0 ? (
                                    <span className="rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5">
                                      {row.metrics_used.join(", ")}
                                    </span>
                                  ) : null}
                                </div>
                              </div>

                              <div className="flex shrink-0 items-center gap-2">
                                <Button
                                  type="button"
                                  variant="outline"
                                  size="sm"
                                  onClick={() => void copyAuditRow(row)}
                                  className="gap-2"
                                >
                                  <Clipboard className="h-4 w-4" />
                                  {copiedAuditId === row.id ? "Copied" : "Copy audit"}
                                </Button>
                              </div>
                            </div>

                            <p className="mt-3 text-xs text-slate-600">
                              <span className="font-semibold text-slate-700">Filters:</span>{" "}
                              {renderFilters(row.filters_applied)}
                            </p>
                          </div>
                        );
                      })}
                    </div>
                  ) : (
                    <div className="mt-4 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600">
                      No EI audit entries yet.
                    </div>
                  )
                ) : null}
              </div>
            </TabsContent>
          </Tabs>
        </div>

        {tab === "ask" ? (
          <form
            className="border-t border-slate-200 px-5 py-4"
            onSubmit={(event) => {
              event.preventDefault();
              void sendMessage(draft);
            }}
          >
            <div className="flex items-center gap-2">
              <input
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                placeholder="Ask about KPIs, trends, or risk signals..."
                className="h-10 flex-1 rounded-lg border border-slate-200 px-3 text-sm text-slate-800 placeholder:text-slate-400 focus:border-slate-300 focus:outline-none focus:ring-2 focus:ring-indigo-200"
              />
              <Button type="submit" disabled={isSending || !draft.trim()} className="h-10 gap-2">
                <Send className="h-4 w-4" />
                Send
              </Button>
            </div>
            <p className="mt-2 text-[11px] text-slate-500">
              Default window: {filters.start ?? "-"} to {filters.end ?? "-"}
            </p>
          </form>
        ) : null}
      </aside>
    </>
  );
}
