"use client";

import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import Link from "next/link";
import useSWR from "swr";

import { SectionCard } from "@/components/page-shell";
import { fetchLatestRevenueSnapshotState, type DashboardState } from "@/lib/api/revenue";
import { safeSnapshotAccess, type JsonRecord, type JsonValue, type RevenueSnapshotResponse } from "@/lib/api/types";

const DASHBOARD_FIELDS: Array<keyof RevenueSnapshotResponse> = [
  "snapshot_id",
  "generated_at",
  "total_exposure_cents",
  "expected_recovery_30_day_cents",
  "short_term_cash_opportunity_cents",
  "high_risk_claim_count",
  "critical_pre_submission_count",
  "top_aggressive_payers",
  "top_revenue_loss_drivers",
  "top_worklist",
];

function isRecord(value: unknown): value is JsonRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function safeJson(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

function formatFieldLabel(field: string): string {
  return field
    .split("_")
    .map((segment) => segment.charAt(0).toUpperCase() + segment.slice(1))
    .join(" ");
}

function formatRetryInterval(intervalMs: number): string {
  const seconds = Math.round(intervalMs / 1000);
  return `${seconds} second${seconds === 1 ? "" : "s"}`;
}

function renderFieldValue(value: JsonValue): ReactNode {
  if (Array.isArray(value) || isRecord(value)) {
    return (
      <pre className="mt-2 overflow-x-auto rounded-md bg-black/40 p-3 text-xs text-zinc-200">
        {safeJson(value)}
      </pre>
    );
  }

  return <p className="mt-2 text-lg font-semibold text-white">{value === null ? "null" : String(value)}</p>;
}

function DashboardSkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {Array.from({ length: DASHBOARD_FIELDS.length }).map((_, index) => (
          <div
            key={`dashboard-skeleton-${index}`}
            className="animate-pulse rounded-lg border border-zinc-800 bg-black/40 p-4"
          >
            <div className="h-3 w-28 rounded bg-zinc-800" />
            <div className="mt-4 h-8 w-40 rounded bg-zinc-700" />
          </div>
        ))}
      </div>
      <div className="h-10 w-28 animate-pulse rounded-md border border-zinc-800 bg-black/40" />
    </div>
  );
}

type DashboardStatusTone = "info" | "warning" | "error";

function getToneClasses(tone: DashboardStatusTone): string {
  switch (tone) {
    case "info":
      return "border-sky-500/40 bg-sky-500/10 text-sky-100";
    case "warning":
      return "border-amber-500/40 bg-amber-500/10 text-amber-100";
    case "error":
      return "border-rose-500/40 bg-rose-500/10 text-rose-100";
  }
}

function BackHomeLink() {
  return (
    <Link href="/" className="inline-flex rounded-md border border-zinc-700 px-4 py-2 text-white transition hover:border-white">
      Back to home
    </Link>
  );
}

function StatusDetail({ detail }: { detail?: string }) {
  if (!detail) {
    return null;
  }

  return (
    <div className="rounded-md border border-white/10 bg-black/20 px-3 py-2 text-xs text-zinc-200">
      <p className="font-medium uppercase tracking-wide text-zinc-400">Details</p>
      <p className="mt-2 whitespace-pre-wrap break-words">{detail}</p>
    </div>
  );
}

function DashboardStatusPanel({
  tone,
  title,
  message,
  detail,
  actions,
  guidance,
}: {
  tone: DashboardStatusTone;
  title: string;
  message: string;
  detail?: string;
  actions?: ReactNode;
  guidance?: ReactNode;
}) {
  return (
    <div className="space-y-6 text-sm text-zinc-300">
      <div className={`space-y-3 rounded-md border px-4 py-3 ${getToneClasses(tone)}`}>
        <div>
          <p className="font-semibold text-white">{title}</p>
          <p className="mt-2 text-sm leading-6">{message}</p>
        </div>
        <StatusDetail detail={detail} />
        {guidance ? <div className="text-xs text-zinc-200">{guidance}</div> : null}
      </div>
      {actions ? <div className="flex flex-wrap gap-3">{actions}</div> : null}
    </div>
  );
}

function SnapshotPendingState({
  message,
  detail,
  retryIntervalMs,
  retriesRemaining,
  onRetry,
}: {
  message: string;
  detail?: string;
  retryIntervalMs: number;
  retriesRemaining: number;
  onRetry: () => void;
}) {
  return (
    <DashboardStatusPanel
      tone="info"
      title="Generating first snapshot"
      message={message}
      detail={detail}
      guidance={
        retriesRemaining > 0
          ? `The dashboard will check again automatically in ${formatRetryInterval(retryIntervalMs)}.`
          : "Automatic checks are paused for now. Use “Check again now” after the backend finishes recovering."
      }
      actions={
        <>
          <button
            type="button"
            onClick={onRetry}
            className="rounded-md border border-zinc-700 px-4 py-2 text-white transition hover:border-white"
          >
            Check again now
          </button>
          <BackHomeLink />
        </>
      }
    />
  );
}

function RecoverableDashboardState({
  message,
  detail,
  retryIntervalMs,
  retriesRemaining,
  onRetry,
}: {
  message: string;
  detail?: string;
  retryIntervalMs: number;
  retriesRemaining: number;
  onRetry: () => void;
}) {
  return (
    <DashboardStatusPanel
      tone="warning"
      title="Snapshot temporarily unavailable"
      message={message}
      detail={detail}
      guidance={
        retriesRemaining > 0
          ? `The UI will retry automatically in ${formatRetryInterval(retryIntervalMs)} while the backend catches up.`
          : "Automatic retries are paused to avoid hammering the backend. Use “Retry” when you're ready."
      }
      actions={
        <>
          <button
            type="button"
            onClick={onRetry}
            className="rounded-md border border-zinc-700 px-4 py-2 text-white transition hover:border-white"
          >
            Retry
          </button>
          <BackHomeLink />
        </>
      }
    />
  );
}

function BackendFailureState({
  message,
  detail,
  onRetry,
}: {
  message: string;
  detail?: string;
  onRetry: () => void;
}) {
  return (
    <DashboardStatusPanel
      tone="error"
      title="Revenue snapshot failed"
      message={message}
      detail={detail}
      guidance="Retry after the backend error is addressed, or refresh once recovery is complete."
      actions={
        <>
          <button
            type="button"
            onClick={onRetry}
            className="rounded-md border border-zinc-700 px-4 py-2 text-white transition hover:border-white"
          >
            Retry
          </button>
          <BackHomeLink />
        </>
      }
    />
  );
}

function FatalDashboardState({
  message,
  detail,
  onRetry,
}: {
  message: string;
  detail?: string;
  onRetry: () => void;
}) {
  return (
    <DashboardStatusPanel
      tone="error"
      title="Unexpected dashboard response"
      message={message}
      detail={detail}
      guidance="The frontend received data it could not safely render. Retry once the response contract is corrected."
      actions={
        <>
          <button
            type="button"
            onClick={onRetry}
            className="rounded-md border border-zinc-700 px-4 py-2 text-white transition hover:border-white"
          >
            Retry
          </button>
          <BackHomeLink />
        </>
      }
    />
  );
}

function UnauthorizedState({ message, detail }: { message: string; detail?: string }) {
  return (
    <DashboardStatusPanel
      tone="warning"
      title="Session expired"
      message={message}
      detail={detail}
      guidance="Sign in again to refresh your session before returning to the dashboard."
      actions={
        <>
          <Link
            href="/login"
            className="inline-flex rounded-md border border-white px-4 py-2 font-medium text-white transition hover:bg-white hover:text-black"
          >
            Go to sign in
          </Link>
          <BackHomeLink />
        </>
      }
    />
  );
}

function DashboardReadyState({ snapshot }: { snapshot: RevenueSnapshotResponse }) {
  const fields = DASHBOARD_FIELDS.flatMap((field) => {
    const value = safeSnapshotAccess(snapshot, field);

    return value === null ? [] : ([[field, value]] as const);
  });

  return (
    <div className="space-y-6 text-sm text-zinc-300">
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {fields.map(([field, value]) => (
          <div key={field} className="rounded-lg border border-zinc-800 bg-black/40 p-4">
            <p className="text-xs uppercase tracking-wide text-zinc-500">{formatFieldLabel(field)}</p>
            {renderFieldValue(value)}
          </div>
        ))}
      </div>
      <BackHomeLink />
    </div>
  );
}

function renderDashboardState(
  state: DashboardState,
  autoRetryCount: number,
  onRetry: () => void,
): ReactNode {
  switch (state.status) {
    case "loading":
      return <DashboardSkeleton />;
    case "pending":
      return (
        <SnapshotPendingState
          message={state.message}
          detail={state.detail}
          retryIntervalMs={state.retryPolicy.intervalMs}
          retriesRemaining={Math.max(state.retryPolicy.maxAttempts - autoRetryCount, 0)}
          onRetry={onRetry}
        />
      );
    case "recoverable":
      return (
        <RecoverableDashboardState
          message={state.message}
          detail={state.detail}
          retryIntervalMs={state.retryPolicy.intervalMs}
          retriesRemaining={Math.max(state.retryPolicy.maxAttempts - autoRetryCount, 0)}
          onRetry={onRetry}
        />
      );
    case "ready":
      return <DashboardReadyState snapshot={state.snapshot} />;
    case "unauthorized":
      return <UnauthorizedState message={state.message} detail={state.detail} />;
    case "backend_failure":
      return <BackendFailureState message={state.message} detail={state.detail} onRetry={onRetry} />;
    case "fatal":
      return <FatalDashboardState message={state.message} detail={state.detail} onRetry={onRetry} />;
    default:
      return (
        <FatalDashboardState
          message="Unable to determine the current dashboard state."
          onRetry={onRetry}
        />
      );
  }
}

export function DashboardContent() {
  const [autoRetryState, setAutoRetryState] = useState<{ key: string; count: number }>({
    key: "idle",
    count: 0,
  });
  const { data, isLoading, mutate } = useSWR("latest-revenue-snapshot", fetchLatestRevenueSnapshotState, {
    revalidateOnFocus: false,
    shouldRetryOnError: false,
  });
  const state: DashboardState = isLoading && !data ? { status: "loading" } : (data ?? { status: "loading" });
  const autoRetryKey =
    state.status === "pending" || state.status === "recoverable"
      ? `${state.status}:${state.message}:${state.detail ?? ""}`
      : "idle";
  const autoRetryCount = autoRetryState.key === autoRetryKey ? autoRetryState.count : 0;
  const autoRetryIntervalMs =
    state.status === "pending" || state.status === "recoverable" ? state.retryPolicy.intervalMs : null;
  const autoRetryLimit = state.status === "pending" || state.status === "recoverable" ? state.retryPolicy.maxAttempts : 0;

  useEffect(() => {
    if (state.status !== "pending" && state.status !== "recoverable") {
      return;
    }

    if (autoRetryIntervalMs === null || autoRetryCount >= autoRetryLimit) {
      return;
    }

    const timeoutId = window.setTimeout(() => {
      setAutoRetryState((currentState) => ({
        key: autoRetryKey,
        count: currentState.key === autoRetryKey ? currentState.count + 1 : 1,
      }));
      void mutate();
    }, autoRetryIntervalMs);

    return () => window.clearTimeout(timeoutId);
  }, [autoRetryCount, autoRetryIntervalMs, autoRetryKey, autoRetryLimit, mutate, state.status]);

  return (
    <SectionCard title="Revenue snapshot">
      {renderDashboardState(state, autoRetryCount, () => {
        setAutoRetryState({
          key: autoRetryKey,
          count: 0,
        });
        void mutate();
      })}
    </SectionCard>
  );
}
