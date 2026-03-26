"use client";

import { startTransition, useCallback, useEffect, useMemo, useState } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";

import type { RevenueWorklistActionResponse } from "@/lib/api/worklist";
import {
  type InsightMetric,
  type QueueItem,
  type QueuePriority,
  type QueueStatus,
} from "@/lib/revenue-os";

const ALL_TYPES = "All types";
const ALL_PRIORITIES = "All priorities";
const ALL_STATUSES = "All statuses";
const DEFAULT_SORT_BY = "priority";
const DEFAULT_SORT_DIRECTION = "desc";
const SAVED_VIEWS = ["Critical priority", "Needs review", "Denials", "Unassigned"] as const;
const SORT_OPTIONS = [
  { value: "priority", label: "Priority" },
  { value: "updated_at", label: "Updated" },
  { value: "created_at", label: "Created" },
  { value: "aging", label: "Aging" },
  { value: "amount_at_risk", label: "Amount at risk" },
] as const;

type SortValue = (typeof SORT_OPTIONS)[number]["value"];
type SortDirection = "asc" | "desc";
type CueTone = "neutral" | "urgent" | "impact" | "escalation";

function formatMoney(cents: number): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(cents / 100);
}

function formatTimestampLabel(value: string | null | undefined): string {
  if (!value) {
    return "Unavailable";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.valueOf())) {
    return value;
  }
  return parsed.toLocaleString();
}

function getPriorityClasses(priority: QueuePriority): string {
  switch (priority) {
    case "critical":
      return "border-rose-400/30 bg-rose-400/10 text-rose-200";
    case "high":
      return "border-amber-400/30 bg-amber-400/10 text-amber-200";
    case "medium":
      return "border-sky-400/30 bg-sky-400/10 text-sky-200";
    case "low":
    default:
      return "border-emerald-400/30 bg-emerald-400/10 text-emerald-200";
  }
}

function getStatusClasses(status: QueueStatus): string {
  switch (status) {
    case "needs_review":
      return "bg-rose-400/10 text-rose-200";
    case "in_progress":
      return "bg-sky-400/10 text-sky-200";
    case "resolved":
      return "bg-slate-400/10 text-slate-200";
    case "open":
    default:
      return "bg-amber-400/10 text-amber-200";
  }
}

function getEscalationClasses(value: string): string {
  switch (value) {
    case "escalated":
      return "border-rose-400/25 bg-rose-400/[0.10] text-rose-100";
    case "watch":
      return "border-amber-400/25 bg-amber-400/[0.10] text-amber-100";
    default:
      return "border-emerald-400/25 bg-emerald-400/[0.10] text-emerald-100";
  }
}

function getConfidenceClasses(confidence: string): string {
  switch (confidence.toLowerCase()) {
    case "high":
      return "border-emerald-400/25 bg-emerald-400/[0.10] text-emerald-100";
    case "medium":
      return "border-amber-400/25 bg-amber-400/[0.10] text-amber-100";
    default:
      return "border-slate-400/25 bg-slate-400/[0.10] text-slate-200";
  }
}

function cueToneClasses(tone: CueTone): string {
  switch (tone) {
    case "urgent":
      return "border-amber-400/20 bg-amber-400/[0.08] text-amber-100";
    case "impact":
      return "border-emerald-400/20 bg-emerald-400/[0.08] text-emerald-100";
    case "escalation":
      return "border-rose-400/20 bg-rose-400/[0.08] text-rose-100";
    case "neutral":
    default:
      return "border-white/10 bg-white/[0.05] text-slate-200";
  }
}

function getSavedViewState(view: string): {
  type?: string;
  priority?: string;
  status?: string;
  search?: string;
} {
  switch (view) {
    case "Critical priority":
      return { priority: "critical" };
    case "Needs review":
      return { status: "needs_review" };
    case "Denials":
      return { type: "DENIAL" };
    case "Unassigned":
      return { search: "unassigned" };
    default:
      return {};
  }
}

function getActiveViewLabel(state: {
  typeFilter: string;
  priorityFilter: string;
  statusFilter: string;
  searchText: string;
}) {
  return (
    SAVED_VIEWS.find((view) => {
      const saved = getSavedViewState(view);
      return (
        (saved.type ?? ALL_TYPES) === state.typeFilter &&
        (saved.priority ?? ALL_PRIORITIES) === state.priorityFilter &&
        (saved.status ?? ALL_STATUSES) === state.statusFilter &&
        (saved.search ?? "") === state.searchText
      );
    }) ?? null
  );
}

function normalizeSortValue(value: string | null | undefined, fallback: SortValue): SortValue {
  return SORT_OPTIONS.some((option) => option.value === value) ? (value as SortValue) : fallback;
}

function normalizeSortDirection(value: string | null | undefined, fallback: SortDirection): SortDirection {
  return value === "asc" || value === "desc" ? value : fallback;
}

function CommandDeck({
  totalItems,
  currentPage,
  totalPages,
  snapshotNotice,
}: {
  totalItems: number;
  currentPage: number;
  totalPages: number;
  snapshotNotice?: string | null;
}) {
  return (
    <section className="overflow-hidden rounded-[30px] border border-white/8 bg-[linear-gradient(135deg,rgba(18,22,31,0.98),rgba(11,14,21,0.98))] shadow-[0_30px_80px_rgba(0,0,0,0.35)]">
      <div className="border-b border-white/8 px-5 py-4 lg:px-7">
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl space-y-2">
            <p className="text-[11px] uppercase tracking-[0.34em] text-sky-200/70">Revenue OS Command Deck</p>
            <div className="space-y-1">
              <h2 className="text-[1.85rem] font-semibold tracking-[-0.06em] text-white lg:text-[2.65rem]">
                Work the queue with less guesswork.
              </h2>
              <p className="max-w-2xl text-sm leading-5.5 text-slate-300">
                Triage what matters, understand why it matters, and move the next safe step using the backend-owned
                workflow contract.
              </p>
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <div className="rounded-[20px] border border-white/8 bg-white/[0.03] px-4 py-3">
              <p className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Queue volume</p>
              <p className="mt-1.5 text-xl font-semibold tracking-[-0.04em] text-white">{totalItems}</p>
              <p className="mt-1 text-xs text-slate-400">Canonical backend work items</p>
            </div>
            <div className="rounded-[20px] border border-white/8 bg-white/[0.03] px-4 py-3">
              <p className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Current page</p>
              <p className="mt-1.5 text-xl font-semibold tracking-[-0.04em] text-white">
                {currentPage}/{Math.max(totalPages, 1)}
              </p>
              <p className="mt-1 text-xs text-slate-400">Server-paginated queue view</p>
            </div>
            <div className="rounded-[20px] border border-white/8 bg-white/[0.03] px-4 py-3">
              <p className="text-[11px] uppercase tracking-[0.24em] text-slate-500">Operator mode</p>
              <p className="mt-1.5 text-base font-semibold tracking-[-0.04em] text-white">Decision support</p>
              <p className="mt-1 text-xs text-slate-400">Recommendation cues stay backend explained</p>
            </div>
          </div>
        </div>
      </div>
      {snapshotNotice ? (
        <div className="px-5 py-3 lg:px-7">
          <div className="rounded-[18px] border border-amber-400/20 bg-amber-400/[0.08] px-4 py-2.5 text-sm leading-6 text-amber-100">
            {snapshotNotice}
          </div>
        </div>
      ) : null}
    </section>
  );
}

function InsightStrip({ metrics }: { metrics: InsightMetric[] }) {
  return (
    <div className="grid gap-4 xl:grid-cols-4">
      {metrics.map((metric) => (
        <div
          key={metric.label}
          className="relative overflow-hidden rounded-[24px] border border-white/8 bg-[linear-gradient(180deg,rgba(20,24,34,0.94),rgba(13,16,24,0.98))] p-3.5"
        >
          <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-sky-300/30 to-transparent" />
          <p className="text-[11px] uppercase tracking-[0.3em] text-slate-500">{metric.label}</p>
          <div className="mt-4 flex items-start justify-between gap-3">
            <div className="space-y-2">
              <p className="text-[1.75rem] font-semibold tracking-[-0.05em] text-white">{metric.value}</p>
              <p className="max-w-[18rem] text-sm leading-5 text-slate-300">{metric.trend}</p>
            </div>
            <span className="rounded-full border border-white/8 bg-white/[0.05] px-3 py-1 text-xs font-medium text-slate-300">
              {metric.change}
            </span>
          </div>
          <p className="mt-4 text-sm font-medium text-sky-200/90">{metric.drillLabel}</p>
        </div>
      ))}
    </div>
  );
}

function FilterBar(props: {
  typeFilter: string;
  priorityFilter: string;
  statusFilter: string;
  searchText: string;
  sortBy: SortValue;
  sortDirection: SortDirection;
  typeOptions: string[];
  activeView: string | null;
  onTypeChange: (value: string) => void;
  onPriorityChange: (value: string) => void;
  onStatusChange: (value: string) => void;
  onSearchChange: (value: string) => void;
  onSortByChange: (value: SortValue) => void;
  onSortDirectionChange: (value: SortDirection) => void;
  onApplySavedView: (view: string) => void;
}) {
  const {
    typeFilter,
    priorityFilter,
    statusFilter,
    searchText,
    sortBy,
    sortDirection,
    typeOptions,
    activeView,
    onTypeChange,
    onPriorityChange,
    onStatusChange,
    onSearchChange,
    onSortByChange,
    onSortDirectionChange,
    onApplySavedView,
  } = props;

  return (
    <div className="space-y-2.5 rounded-[22px] border border-white/8 bg-white/[0.03] p-3 backdrop-blur-sm">
      <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
        <div className="flex flex-wrap items-center gap-2">
          {SAVED_VIEWS.map((view) => {
            const active = activeView === view;
            return (
              <button
                key={view}
                type="button"
                onClick={() => onApplySavedView(view)}
                className={`rounded-full border px-3 py-2 text-sm transition ${
                  active
                    ? "border-white/14 bg-white/[0.12] text-white"
                    : "border-white/8 bg-white/[0.04] text-slate-300 hover:border-white/14 hover:bg-white/[0.08]"
                }`}
              >
                {view}
              </button>
            );
          })}
        </div>
        <p className="text-xs uppercase tracking-[0.24em] text-slate-500">Server-generated workflow state</p>
      </div>

      <div className="grid gap-3 xl:grid-cols-[minmax(0,1.5fr)_repeat(5,minmax(150px,0.7fr))]">
        <label className="rounded-[18px] border border-white/8 bg-[#12161f] px-4 py-3">
          <span className="text-[11px] uppercase tracking-[0.22em] text-slate-500">Search</span>
          <input
            value={searchText}
            onChange={(event) => onSearchChange(event.target.value)}
            placeholder="Claim, payer, patient, type, reason, or assignee"
            className="mt-2 w-full bg-transparent text-sm text-slate-200 outline-none placeholder:text-slate-500"
          />
        </label>

        <label className="rounded-[18px] border border-white/8 bg-[#12161f] px-4 py-3">
          <span className="text-[11px] uppercase tracking-[0.22em] text-slate-500">Type</span>
          <select
            value={typeFilter}
            onChange={(event) => onTypeChange(event.target.value)}
            className="mt-2 w-full bg-transparent text-sm text-slate-200 outline-none"
          >
            <option value={ALL_TYPES}>All types</option>
            {typeOptions.map((type) => (
              <option key={type} value={type}>
                {type}
              </option>
            ))}
          </select>
        </label>

        <label className="rounded-[18px] border border-white/8 bg-[#12161f] px-4 py-3">
          <span className="text-[11px] uppercase tracking-[0.22em] text-slate-500">Priority</span>
          <select
            value={priorityFilter}
            onChange={(event) => onPriorityChange(event.target.value)}
            className="mt-2 w-full bg-transparent text-sm text-slate-200 outline-none"
          >
            <option value={ALL_PRIORITIES}>All priorities</option>
            <option value="critical">Critical</option>
            <option value="high">High</option>
            <option value="medium">Medium</option>
            <option value="low">Low</option>
          </select>
        </label>

        <label className="rounded-[18px] border border-white/8 bg-[#12161f] px-4 py-3">
          <span className="text-[11px] uppercase tracking-[0.22em] text-slate-500">Status</span>
          <select
            value={statusFilter}
            onChange={(event) => onStatusChange(event.target.value)}
            className="mt-2 w-full bg-transparent text-sm text-slate-200 outline-none"
          >
            <option value={ALL_STATUSES}>All statuses</option>
            <option value="open">Open</option>
            <option value="in_progress">In progress</option>
            <option value="needs_review">Needs review</option>
            <option value="resolved">Resolved</option>
          </select>
        </label>

        <label className="rounded-[18px] border border-white/8 bg-[#12161f] px-4 py-3">
          <span className="text-[11px] uppercase tracking-[0.22em] text-slate-500">Sort</span>
          <select
            value={sortBy}
            onChange={(event) => onSortByChange(event.target.value as SortValue)}
            className="mt-2 w-full bg-transparent text-sm text-slate-200 outline-none"
          >
            {SORT_OPTIONS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </label>

        <label className="rounded-[18px] border border-white/8 bg-[#12161f] px-4 py-3">
          <span className="text-[11px] uppercase tracking-[0.22em] text-slate-500">Direction</span>
          <select
            value={sortDirection}
            onChange={(event) => onSortDirectionChange(event.target.value as SortDirection)}
            className="mt-2 w-full bg-transparent text-sm text-slate-200 outline-none"
          >
            <option value="desc">Descending</option>
            <option value="asc">Ascending</option>
          </select>
        </label>
      </div>

      <p className="text-sm text-slate-400">
        Search, type, status, priority, sorting, and pagination all query the backend worklist API.
      </p>
    </div>
  );
}

function BulkActionBar(props: {
  selectedCount: number;
  hiddenSelectedCount: number;
  isSubmitting: boolean;
  onMarkInProgress: () => void;
  onClearSelection: () => void;
}) {
  const { selectedCount, hiddenSelectedCount, isSubmitting, onMarkInProgress, onClearSelection } = props;

  if (selectedCount === 0) {
    return null;
  }

  return (
    <div className="flex flex-col gap-3 rounded-[22px] border border-sky-400/20 bg-sky-400/[0.05] px-4 py-2.5 backdrop-blur-sm xl:flex-row xl:items-center xl:justify-between">
      <div className="space-y-1">
        <p className="text-sm font-semibold text-white">{selectedCount} work item{selectedCount === 1 ? "" : "s"} selected</p>
        <p className="text-sm text-slate-300">
          Bulk actions are limited to backend-supported workflow actions.
          {hiddenSelectedCount > 0 ? ` ${hiddenSelectedCount} selected item(s) are hidden by the current filters.` : ""}
        </p>
      </div>
      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          onClick={onMarkInProgress}
          disabled={isSubmitting}
          className="rounded-full border border-white/10 bg-white/[0.05] px-3 py-2 text-sm text-white disabled:cursor-not-allowed disabled:opacity-60 hover:-translate-y-[1px] hover:border-white/18 hover:bg-white/[0.09]"
        >
          {isSubmitting ? "Updating..." : "Mark in progress"}
        </button>
        <button
          type="button"
          onClick={onClearSelection}
          disabled={isSubmitting}
          className="rounded-full border border-white/8 px-3 py-2 text-sm text-slate-300 disabled:cursor-not-allowed disabled:opacity-60 hover:border-white/18 hover:text-white"
        >
          Clear
        </button>
      </div>
    </div>
  );
}

function PaginationBar({
  currentPage,
  totalPages,
  totalItems,
  pageSize,
  visibleCount,
  onPageChange,
}: {
  currentPage: number;
  totalPages: number;
  totalItems: number;
  pageSize: number;
  visibleCount: number;
  onPageChange: (page: number) => void;
}) {
  return (
    <div className="flex flex-col gap-3 rounded-[22px] border border-white/8 bg-white/[0.03] px-4 py-2.5 backdrop-blur-sm xl:flex-row xl:items-center xl:justify-between">
      <div className="space-y-1 text-sm text-slate-300">
        <p className="font-medium text-white">
          Server page {currentPage} of {Math.max(totalPages, 1)}
        </p>
        <p>
          {totalItems} canonical work item{totalItems === 1 ? "" : "s"} on the backend. Showing {visibleCount} row
          {visibleCount === 1 ? "" : "s"} from a {pageSize}-item page.
        </p>
      </div>
      <div className="flex gap-2">
        <button
          type="button"
          onClick={() => onPageChange(currentPage - 1)}
          disabled={currentPage <= 1}
          className="rounded-full border border-white/8 px-3 py-2 text-sm text-slate-300 disabled:cursor-not-allowed disabled:opacity-50 hover:border-white/18 hover:text-white"
        >
          Previous
        </button>
        <button
          type="button"
          onClick={() => onPageChange(currentPage + 1)}
          disabled={currentPage >= totalPages}
          className="rounded-full border border-white/8 px-3 py-2 text-sm text-slate-300 disabled:cursor-not-allowed disabled:opacity-50 hover:border-white/18 hover:text-white"
        >
          Next
        </button>
      </div>
    </div>
  );
}

function QueueCuePill({
  label,
  tone = "neutral",
}: {
  label: string;
  tone?: CueTone;
}) {
  return (
    <span className={`rounded-full border px-2.5 py-1 text-[11px] font-medium ${cueToneClasses(tone)}`}>{label}</span>
  );
}

function WorkQueuePanel(props: {
  items: QueueItem[];
  selectedId: string | null;
  selectedIds: string[];
  onSelect: (item: QueueItem) => void;
  onToggleSelect: (itemId: string) => void;
  onToggleSelectVisible: () => void;
}) {
  const { items, selectedId, selectedIds, onSelect, onToggleSelect, onToggleSelectVisible } = props;
  const visibleIds = items.map((item) => item.id);
  const allVisibleSelected = visibleIds.length > 0 && visibleIds.every((id) => selectedIds.includes(id));

  return (
    <div className="overflow-hidden rounded-[28px] border border-white/8 bg-[linear-gradient(180deg,rgba(18,22,30,0.98),rgba(13,16,23,0.98))] backdrop-blur-sm">
      <div className="flex flex-col gap-4 border-b border-white/8 px-5 py-5 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <p className="text-[11px] uppercase tracking-[0.28em] text-slate-500">Queue rail</p>
          <h3 className="mt-1 text-lg font-semibold text-white">Scan urgency, impact, and next step at once</h3>
        </div>
        <div className="flex flex-wrap gap-2 text-sm">
          <button
            type="button"
            onClick={onToggleSelectVisible}
            className="rounded-full border border-white/10 px-3 py-2 text-slate-300 hover:-translate-y-[1px] hover:border-white/20 hover:text-white"
          >
            {allVisibleSelected ? "Clear visible" : "Select visible"}
          </button>
        </div>
      </div>

      <div className="divide-y divide-white/6" aria-label="Canonical revenue work items">
        {items.length === 0 ? (
          <div className="px-5 py-12 text-center text-sm text-slate-400">No backend work items match the current filters.</div>
        ) : null}

        {items.map((item) => {
          const rowSelected = item.id === selectedId;
          const checked = selectedIds.includes(item.id);
          const identity = item.subtitle || [item.patient, item.payer].filter(Boolean).join(" · ");
          const assigneeLabel = item.assignee.userName ?? item.assignee.teamLabel ?? "Unassigned";
          const leadUrgencyCue = item.recommendedAction.urgency_cues[0];
          const leadImpactCue = item.recommendedAction.impact_cues[0];
          const leadEscalationCue = item.recommendedAction.escalation_signals[0];

          return (
            <div
              key={item.id}
              tabIndex={0}
              onClick={() => onSelect(item)}
              onKeyDown={(event) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  onSelect(item);
                }
              }}
              className={`px-5 py-5 outline-none transition focus-visible:ring-2 focus-visible:ring-sky-300/60 focus-visible:ring-inset ${
                rowSelected
                  ? "bg-[linear-gradient(90deg,rgba(56,189,248,0.12),rgba(255,255,255,0.02))] ring-1 ring-sky-300/35"
                  : "hover:bg-white/[0.03]"
              }`}
            >
              <div className="rounded-[22px] transition">
                <div className="flex gap-4">
                <div className="pt-1" onClick={(event) => event.stopPropagation()}>
                  <button
                    type="button"
                    onClick={() => onToggleSelect(item.id)}
                    onKeyDown={(event) => {
                      if (event.key === "Enter" || event.key === " ") {
                        event.stopPropagation();
                      }
                    }}
                    className={`flex h-5 w-5 items-center justify-center rounded border text-[10px] ${
                      checked
                        ? "border-sky-300/30 bg-sky-300/15 text-sky-100"
                        : "border-white/10 bg-white/[0.03] text-transparent"
                    }`}
                    aria-label={`Select ${item.title}`}
                  >
                    ✓
                  </button>
                </div>

                <div className="min-w-0 flex-1 space-y-4">
                  <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
                    <div className="min-w-0 space-y-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="truncate text-base font-semibold tracking-[-0.02em] text-white">{item.title}</span>
                        <span className={`rounded-full px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.18em] ${getStatusClasses(item.status)}`}>
                          {item.status.replace("_", " ")}
                        </span>
                        <span
                          className={`rounded-full border px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.18em] ${getPriorityClasses(item.priority)}`}
                        >
                          {item.priority}
                        </span>
                        <span
                          className={`rounded-full border px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.18em] ${getEscalationClasses(item.escalationState)}`}
                        >
                          {item.escalationState}
                        </span>
                      </div>
                      <p className="max-w-3xl text-sm leading-6 text-slate-200">{item.reason}</p>
                      <p className="text-xs uppercase tracking-[0.18em] text-slate-500">{identity || item.payer}</p>
                    </div>

                    <div className="grid shrink-0 gap-2 rounded-[22px] border border-white/8 bg-black/20 px-4 py-3 text-sm xl:min-w-[250px]">
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-slate-500">At risk</span>
                        <span className="font-semibold text-white">{formatMoney(item.amountAtRiskCents)}</span>
                      </div>
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-slate-500">SLA</span>
                        <span className="text-slate-200">{item.slaState}</span>
                      </div>
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-slate-500">Aging</span>
                        <span className="text-slate-200">{item.agingDays}d · {item.agingBucket}</span>
                      </div>
                      <div className="flex items-center justify-between gap-3">
                        <span className="text-slate-500">Assignee</span>
                        <span className="truncate text-slate-200">{assigneeLabel}</span>
                      </div>
                    </div>
                  </div>

                  <div className="flex flex-wrap items-center gap-2">
                    <QueueCuePill label={item.recommendedAction.type} />
                    <QueueCuePill label={item.type} />
                    <QueueCuePill label={`SLA ${item.slaState}`} />
                    {leadUrgencyCue ? <QueueCuePill label={leadUrgencyCue} tone="urgent" /> : null}
                    {leadImpactCue ? <QueueCuePill label={leadImpactCue} tone="impact" /> : null}
                    {leadEscalationCue ? <QueueCuePill label={leadEscalationCue} tone="escalation" /> : null}
                  </div>
                </div>
              </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function RecommendationCueGroup({
  title,
  items,
  tone = "neutral",
}: {
  title: string;
  items: string[];
  tone?: "neutral" | "urgent" | "impact" | "escalation";
}) {
  if (items.length === 0) {
    return null;
  }

  return (
    <div className="space-y-3 rounded-[22px] border border-white/8 bg-black/20 p-4">
      <div className="flex items-center justify-between gap-3">
        <h5 className="text-[11px] font-medium uppercase tracking-[0.22em] text-slate-500">{title}</h5>
        <span className="rounded-full border border-white/8 px-2 py-0.5 text-[10px] uppercase tracking-[0.18em] text-slate-500">
          {items.length}
        </span>
      </div>
      <div className="flex flex-wrap gap-2">
        {items.map((entry) => (
          <span
            key={`${title}-${entry}`}
            className={`rounded-2xl border px-3 py-2 text-xs leading-5 ${cueToneClasses(tone)}`}
          >
            {entry}
          </span>
        ))}
      </div>
    </div>
  );
}

function WorkflowFact({
  label,
  value,
}: {
  label: string;
  value: string;
}) {
  return (
    <div className="rounded-[20px] border border-white/8 bg-black/20 px-4 py-4">
      <p className="text-[11px] uppercase tracking-[0.22em] text-slate-500">{label}</p>
      <p className="mt-2 break-words text-sm leading-6 text-white">{value}</p>
    </div>
  );
}

function DecisionSupportPanel({
  item,
  isSubmitting,
  onMarkInProgress,
}: {
  item: QueueItem | null;
  isSubmitting: boolean;
  onMarkInProgress: (itemIds: string[]) => Promise<RevenueWorklistActionResponse>;
}) {
  if (!item) {
    return (
      <div className="rounded-[24px] border border-dashed border-white/8 bg-white/[0.02] p-5 text-sm text-slate-400">
        Decision support appears when a backend work item is selected.
      </div>
    );
  }

  const canMarkInProgress = item.allowedActions.includes("mark_in_progress");
  const assigneeLabel = item.assignee.userName ?? item.assignee.teamLabel ?? "Unassigned";
  const identity = item.subtitle || [item.patient, item.payer].filter(Boolean).join(" · ");

  return (
    <div className="space-y-5 rounded-[28px] border border-white/8 bg-[linear-gradient(180deg,rgba(22,26,34,0.98),rgba(15,18,25,0.99))] p-5 backdrop-blur-sm">
      <div className="space-y-4">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div className="space-y-3">
            <div className="space-y-2">
              <p className="text-[11px] uppercase tracking-[0.28em] text-slate-500">Operator inspector</p>
              <h3 className="text-2xl font-semibold tracking-[-0.05em] text-white">{item.title}</h3>
            </div>
            <p className="max-w-3xl text-sm leading-6 text-slate-300">{item.reason}</p>
            <p className="text-xs uppercase tracking-[0.18em] text-slate-500">{identity || item.payer}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <span className={`rounded-full px-3 py-1 text-[11px] font-medium uppercase tracking-[0.2em] ${getStatusClasses(item.status)}`}>
              {item.status.replace("_", " ")}
            </span>
            <span
              className={`rounded-full border px-3 py-1 text-[11px] font-medium uppercase tracking-[0.2em] ${getPriorityClasses(item.priority)}`}
            >
              {item.priority}
            </span>
            <span
              className={`rounded-full border px-3 py-1 text-[11px] font-medium uppercase tracking-[0.2em] ${getEscalationClasses(item.escalationState)}`}
            >
              {item.escalationState}
            </span>
            <span className="rounded-full border border-white/10 bg-white/[0.05] px-3 py-1 text-[11px] font-medium uppercase tracking-[0.2em] text-slate-200">
              {item.agingBucket}
            </span>
          </div>
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <WorkflowFact label="Amount at risk" value={formatMoney(item.amountAtRiskCents)} />
        <WorkflowFact label="Aging / SLA" value={`${item.agingDays}d · ${item.slaState}`} />
        <WorkflowFact label="Assignee" value={assigneeLabel} />
        <WorkflowFact label="Payer / facility" value={[item.payer, item.facility].filter(Boolean).join(" · ") || "Unavailable"} />
      </div>

      <div className="space-y-4 rounded-[24px] border border-sky-300/12 bg-sky-300/[0.05] p-5">
        <div className="flex flex-col gap-3 xl:flex-row xl:items-start xl:justify-between">
          <div className="space-y-2">
            <p className="text-[11px] uppercase tracking-[0.24em] text-sky-200/70">Recommended next step</p>
            <h4 className="text-lg font-semibold text-white">{item.recommendedAction.type}</h4>
          </div>
          <span
            className={`rounded-full border px-3 py-1 text-[11px] font-medium uppercase tracking-[0.2em] ${getConfidenceClasses(item.recommendedAction.confidence)}`}
          >
            {item.recommendedAction.confidence} confidence
          </span>
        </div>
        <div className="space-y-3 text-sm text-white">
          <p className="text-base leading-7 text-white">{item.recommendedAction.reason}</p>
          {item.recommendedAction.rationale ? (
            <p className="leading-6 text-slate-300">{item.recommendedAction.rationale}</p>
          ) : null}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {item.allowedActions.map((action) => (
            <span key={action} className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-2 text-sm text-white">
              {action}
            </span>
          ))}
          {canMarkInProgress ? (
            <button
              type="button"
              onClick={() => void onMarkInProgress([item.id])}
              disabled={isSubmitting}
              className="rounded-full border border-white/10 bg-white/[0.08] px-4 py-2 text-sm font-medium text-white disabled:cursor-not-allowed disabled:opacity-60 hover:border-white/18 hover:bg-white/[0.12]"
            >
              {isSubmitting ? "Updating..." : "Mark in progress"}
            </button>
          ) : null}
        </div>
      </div>

      {item.recommendedAction.decision_drivers.length > 0 ||
      item.recommendedAction.urgency_cues.length > 0 ||
      item.recommendedAction.impact_cues.length > 0 ||
      item.recommendedAction.escalation_signals.length > 0 ? (
        <div className="space-y-4">
          <div className="flex items-center justify-between gap-3">
            <h4 className="text-sm font-semibold text-white">Decision signals</h4>
            <span className="text-xs uppercase tracking-[0.18em] text-slate-500">Backend explained</span>
          </div>
          <div className="grid gap-3 xl:grid-cols-2">
            <RecommendationCueGroup title="Decision drivers" items={item.recommendedAction.decision_drivers} />
            <RecommendationCueGroup title="Urgency cues" items={item.recommendedAction.urgency_cues} tone="urgent" />
            <RecommendationCueGroup title="Impact cues" items={item.recommendedAction.impact_cues} tone="impact" />
            <RecommendationCueGroup title="Escalation signals" items={item.recommendedAction.escalation_signals} tone="escalation" />
          </div>
        </div>
      ) : null}

      <div className="space-y-3 rounded-[24px] border border-white/8 bg-black/20 p-4">
        <div className="flex items-center justify-between gap-3">
          <h4 className="text-sm font-semibold text-white">Workflow context</h4>
          <span className="rounded-full border border-white/8 px-2 py-1 text-[10px] uppercase tracking-[0.2em] text-slate-400">
            Server enforced
          </span>
        </div>
        <div className="grid gap-3 sm:grid-cols-2">
          <WorkflowFact label="Type" value={item.type} />
          <WorkflowFact label="Patient" value={item.patient ?? "Unavailable"} />
        </div>
        <div className="space-y-3">
          <h5 className="text-[11px] uppercase tracking-[0.22em] text-slate-500">Reason codes</h5>
          <div className="flex flex-wrap gap-2">
            {item.reasonCodes.map((code) => (
              <span key={code} className="rounded-full border border-white/10 bg-white/[0.05] px-3 py-1 text-xs text-slate-200">
                {code}
              </span>
            ))}
          </div>
        </div>
        {!canMarkInProgress ? (
          <div className="rounded-[18px] border border-amber-400/20 bg-amber-400/[0.08] px-4 py-3 text-sm leading-6 text-amber-100">
            No direct action is available from this panel right now. Use the backend recommendation and workflow
            context to guide the next operational step.
          </div>
        ) : null}
      </div>

      <div className="space-y-3">
        <div className="flex items-center justify-between gap-3">
          <h4 className="text-sm font-semibold text-white">Timeline</h4>
          <span className="text-sm text-slate-500">Projection trace</span>
        </div>
        <div className="space-y-3">
          {item.timeline.map((entry) => (
            <div key={`${entry.at}-${entry.event}`} className="rounded-2xl border border-white/8 bg-black/20 p-3">
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-medium text-white">{entry.event}</p>
                <span className="text-xs text-slate-500">{formatTimestampLabel(entry.at)}</span>
              </div>
              <p className="mt-1 text-sm text-slate-400">{entry.detail}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

export function RevenueWorkbench({
  items,
  metrics,
  typeOptions,
  totalItems,
  currentPage,
  pageSize,
  totalPages,
  sortBy,
  sortDirection,
  snapshotNotice,
  onMarkInProgress,
}: {
  items: QueueItem[];
  metrics: InsightMetric[];
  typeOptions: string[];
  totalItems: number;
  currentPage: number;
  pageSize: number;
  totalPages: number;
  sortBy: string;
  sortDirection: string;
  snapshotNotice?: string | null;
  onMarkInProgress: (itemIds: string[]) => Promise<RevenueWorklistActionResponse>;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [bulkFeedback, setBulkFeedback] = useState<{ tone: "success" | "error"; message: string } | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const typeFilter = searchParams.get("type") ?? ALL_TYPES;
  const priorityFilter = searchParams.get("priority") ?? ALL_PRIORITIES;
  const statusFilter = searchParams.get("status") ?? ALL_STATUSES;
  const searchText = searchParams.get("search") ?? "";
  const selectedId = searchParams.get("selected");
  const activeSortBy = normalizeSortValue(searchParams.get("sort_by") ?? sortBy, normalizeSortValue(sortBy, DEFAULT_SORT_BY));
  const activeSortDirection = normalizeSortDirection(
    searchParams.get("sort_direction") ?? sortDirection,
    normalizeSortDirection(sortDirection, DEFAULT_SORT_DIRECTION),
  );
  const activePage = Number.parseInt(searchParams.get("page") ?? String(currentPage), 10) || currentPage;

  const activeView = useMemo(
    () => getActiveViewLabel({ typeFilter, priorityFilter, statusFilter, searchText }),
    [priorityFilter, searchText, statusFilter, typeFilter],
  );

  const updateQuery = useCallback(
    (updates: Record<string, string | null>) => {
      const params = new URLSearchParams(searchParams.toString());
      const resetPage = Object.keys(updates).some((key) =>
        ["type", "priority", "status", "search", "sort_by", "sort_direction"].includes(key),
      );

      Object.entries(updates).forEach(([key, value]) => {
        const shouldDelete =
          value === null ||
          value === "" ||
          value === ALL_TYPES ||
          value === ALL_PRIORITIES ||
          value === ALL_STATUSES ||
          (key === "sort_by" && value === DEFAULT_SORT_BY) ||
          (key === "sort_direction" && value === DEFAULT_SORT_DIRECTION) ||
          (key === "page" && value === "1");
        if (shouldDelete) {
          params.delete(key);
        } else {
          params.set(key, value);
        }
      });

      if (resetPage && !Object.prototype.hasOwnProperty.call(updates, "page")) {
        params.delete("page");
      }
      if (resetPage && !Object.prototype.hasOwnProperty.call(updates, "selected")) {
        params.delete("selected");
      }

      const nextUrl = params.toString() ? `${pathname}?${params.toString()}` : pathname;
      startTransition(() => {
        router.replace(nextUrl, { scroll: false });
      });
    },
    [pathname, router, searchParams],
  );

  useEffect(() => {
    const nextSelectedId = items[0]?.id ?? null;
    if (items.length === 0) {
      if (selectedId) {
        updateQuery({ selected: null });
      }
      return;
    }
    if (!selectedId || !items.some((item) => item.id === selectedId)) {
      updateQuery({ selected: nextSelectedId });
    }
  }, [items, selectedId, updateQuery]);

  useEffect(() => {
    if (!bulkFeedback) {
      return;
    }
    const timeout = window.setTimeout(() => setBulkFeedback(null), 4000);
    return () => window.clearTimeout(timeout);
  }, [bulkFeedback]);

  const selectedItem = items.find((item) => item.id === selectedId) ?? items[0] ?? null;
  const hiddenSelectedCount = selectedIds.filter((id) => !items.some((item) => item.id === id)).length;

  async function handleMarkInProgress(itemIds: string[]) {
    if (itemIds.length === 0 || isSubmitting) {
      return {
        action: "mark_in_progress",
        updated_work_item_ids: [],
        updated_count: 0,
        failed_count: 0,
        results: [],
      };
    }

    try {
      setIsSubmitting(true);
      const response = await onMarkInProgress(itemIds);
      const updatedCount = response.updated_count ?? 0;
      const failedCount = response.failed_count ?? 0;
      const failedResults = response.results.filter((result) => result.status !== "completed");
      const firstFailure = failedResults[0]?.error_message?.trim();

      if (updatedCount > 0 && failedCount === 0) {
        setBulkFeedback({
          tone: "success",
          message: `Marked ${updatedCount} work item${updatedCount === 1 ? "" : "s"} in progress.`,
        });
      } else if (updatedCount > 0 && failedCount > 0) {
        setBulkFeedback({
          tone: "success",
          message: `${updatedCount} item${updatedCount === 1 ? "" : "s"} updated, ${failedCount} failed.${firstFailure ? ` ${firstFailure}` : ""}`,
        });
      } else {
        setBulkFeedback({
          tone: "error",
          message: firstFailure || "No selected work items could be updated.",
        });
      }

      const successfulIds = new Set(
        response.results.filter((result) => result.status === "completed").map((result) => result.work_item_id),
      );
      setSelectedIds((current) => current.filter((id) => !successfulIds.has(id)));
      return response;
    } catch (error) {
      setBulkFeedback({
        tone: "error",
        message:
          error instanceof Error && error.message.trim()
            ? error.message
            : "Unable to update the selected work items right now.",
      });
      throw error;
    } finally {
      setIsSubmitting(false);
    }
  }

  function toggleSelect(itemId: string) {
    setSelectedIds((current) => (current.includes(itemId) ? current.filter((id) => id !== itemId) : [...current, itemId]));
  }

  function toggleSelectVisible() {
    const visibleIds = items.map((item) => item.id);
    const allVisibleSelected = visibleIds.length > 0 && visibleIds.every((id) => selectedIds.includes(id));
    setSelectedIds((current) =>
      allVisibleSelected ? current.filter((id) => !visibleIds.includes(id)) : Array.from(new Set([...current, ...visibleIds])),
    );
  }

  function applySavedView(view: string) {
    const nextState = getSavedViewState(view);
    updateQuery({
      type: nextState.type ?? null,
      priority: nextState.priority ?? null,
      status: nextState.status ?? null,
      search: nextState.search ?? null,
    });
  }

  function changePage(nextPage: number) {
    if (nextPage < 1 || nextPage > totalPages || nextPage === activePage) {
      return;
    }
    updateQuery({ page: String(nextPage) });
  }

  return (
    <div className="space-y-6">
      <CommandDeck
        totalItems={totalItems}
        currentPage={activePage}
        totalPages={Math.max(totalPages, 1)}
        snapshotNotice={snapshotNotice}
      />

      <InsightStrip metrics={metrics} />

      <FilterBar
        typeFilter={typeFilter}
        priorityFilter={priorityFilter}
        statusFilter={statusFilter}
        searchText={searchText}
        sortBy={activeSortBy}
        sortDirection={activeSortDirection}
        typeOptions={typeOptions}
        activeView={activeView}
        onTypeChange={(value) => updateQuery({ type: value })}
        onPriorityChange={(value) => updateQuery({ priority: value })}
        onStatusChange={(value) => updateQuery({ status: value })}
        onSearchChange={(value) => updateQuery({ search: value })}
        onSortByChange={(value) => updateQuery({ sort_by: value })}
        onSortDirectionChange={(value) => updateQuery({ sort_direction: value })}
        onApplySavedView={applySavedView}
      />

      <BulkActionBar
        selectedCount={selectedIds.length}
        hiddenSelectedCount={hiddenSelectedCount}
        isSubmitting={isSubmitting}
        onMarkInProgress={() => void handleMarkInProgress(selectedIds)}
        onClearSelection={() => setSelectedIds([])}
      />

      {bulkFeedback ? (
        <div
          className={`rounded-[20px] px-4 py-3 text-sm ${
            bulkFeedback.tone === "success"
              ? "border border-emerald-400/20 bg-emerald-400/[0.08] text-emerald-100"
              : "border border-rose-400/20 bg-rose-400/[0.08] text-rose-100"
          }`}
        >
          {bulkFeedback.message}
        </div>
      ) : null}

      <PaginationBar
        currentPage={activePage}
        totalPages={Math.max(totalPages, 1)}
        totalItems={totalItems}
        pageSize={pageSize}
        visibleCount={items.length}
        onPageChange={changePage}
      />

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.18fr)_minmax(420px,0.92fr)]">
        <WorkQueuePanel
          items={items}
          selectedId={selectedItem?.id ?? null}
          selectedIds={selectedIds}
          onSelect={(item) => updateQuery({ selected: item.id })}
          onToggleSelect={toggleSelect}
          onToggleSelectVisible={toggleSelectVisible}
        />
        <DecisionSupportPanel item={selectedItem} isSubmitting={isSubmitting} onMarkInProgress={handleMarkInProgress} />
      </div>
    </div>
  );
}
