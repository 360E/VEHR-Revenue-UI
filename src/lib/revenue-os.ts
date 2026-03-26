import type { RevenueWorklistItem, RevenueWorklistPage } from "@/lib/api/worklist";

export type QueuePriority = "critical" | "high" | "medium" | "low";
export type QueueStatus = "open" | "in_progress" | "needs_review" | "resolved";

export type WorklistTimelineEntry = {
  at: string;
  event: string;
  detail: string;
};

export type WorklistAssignee = {
  userId: string | null;
  userName: string | null;
  teamId: string | null;
  teamLabel: string | null;
};

export type WorklistAction = {
  type: string;
  confidence: string;
  reason: string;
};

export type QueueItem = {
  id: string;
  title: string;
  reason: string;
  subtitle: string | null;
  claimId: string;
  claimRecordId: string | null;
  patient: string | null;
  patientId: string | null;
  payer: string;
  facility: string | null;
  type: string;
  status: QueueStatus;
  priority: QueuePriority;
  agingDays: number;
  agingBucket: string;
  amountAtRiskCents: number;
  slaState: string;
  escalationState: string;
  createdAt: string;
  updatedAt: string;
  recommendedAction: WorklistAction;
  allowedActions: string[];
  reasonCodes: string[];
  assignee: WorklistAssignee;
  timeline: WorklistTimelineEntry[];
};

export type InsightMetric = {
  label: string;
  value: string;
  trend: string;
  change: string;
  drillLabel: string;
};

function formatMoney(cents: number): string {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" }).format(cents / 100);
}

function safePriority(value: string): QueuePriority {
  switch (value) {
    case "critical":
    case "high":
    case "medium":
    case "low":
      return value;
    default:
      return "low";
  }
}

function safeStatus(value: string): QueueStatus {
  switch (value) {
    case "open":
    case "in_progress":
    case "needs_review":
    case "resolved":
      return value;
    default:
      return "needs_review";
  }
}

function itemLabel(item: RevenueWorklistItem): string {
  return item.claim_ref?.trim() || item.claim_id?.trim() || item.id;
}

export function buildRevenueQueueItems(worklist: RevenueWorklistPage): QueueItem[] {
  return worklist.items.map((item) => ({
    id: item.id,
    title: item.title,
    reason: item.reason,
    subtitle: item.subtitle ?? null,
    claimId: itemLabel(item),
    claimRecordId: item.claim_id ?? null,
    patient: item.patient_name ?? null,
    patientId: item.patient_id ?? null,
    payer: item.payer?.trim() || "Payer pending",
    facility: item.facility ?? null,
    type: item.type,
    status: safeStatus(item.status),
    priority: safePriority(item.priority),
    agingDays: Math.max(item.aging_days ?? 0, 0),
    agingBucket: item.aging_bucket,
    amountAtRiskCents: item.amount_at_risk_cents,
    slaState: item.sla_state,
    escalationState: item.escalation_state,
    createdAt: item.created_at,
    updatedAt: item.updated_at,
    recommendedAction: item.recommended_action,
    allowedActions: item.allowed_actions,
    reasonCodes: item.reason_codes,
    assignee: {
      userId: item.assignee.user_id ?? null,
      userName: item.assignee.user_name ?? null,
      teamId: item.assignee.team_id ?? null,
      teamLabel: item.assignee.team_label ?? null,
    },
    timeline: item.timeline_summary.map((entry) => ({
      at: entry.at,
      event: entry.event,
      detail: entry.detail,
    })),
  }));
}

export function buildInsightMetrics(worklist: RevenueWorklistPage): InsightMetric[] {
  const criticalCount = worklist.summary.priority_counts.critical ?? 0;
  const highCount = worklist.summary.priority_counts.high ?? 0;
  const mediumCount = worklist.summary.priority_counts.medium ?? 0;
  const needsReviewCount = worklist.summary.needs_review_count ?? 0;
  const preSubmissionCount = worklist.summary.type_counts.PRE_SUBMISSION_GAP ?? 0;
  const totalAtRiskCents = worklist.summary.total_amount_at_risk_cents ?? 0;

  return [
    {
      label: "Open exposure",
      value: formatMoney(totalAtRiskCents),
      trend: `${worklist.total} server-generated work item${worklist.total === 1 ? "" : "s"} in the queue`,
      change: `${criticalCount} critical`,
      drillLabel: "Review canonical worklist",
    },
    {
      label: "Priority watchlist",
      value: String(highCount + criticalCount),
      trend: "High and critical items from the canonical backend queue",
      change: `${mediumCount} medium`,
      drillLabel: "Inspect urgent work",
    },
    {
      label: "Needs review",
      value: String(needsReviewCount),
      trend: "Files or claims that require human review before clean completion",
      change: `${needsReviewCount} review-required`,
      drillLabel: "Focus review-required work",
    },
    {
      label: "Pre-submission gaps",
      value: String(preSubmissionCount),
      trend: "Workflow items surfaced before clean claim resolution",
      change: `${preSubmissionCount} queue item${preSubmissionCount === 1 ? "" : "s"}`,
      drillLabel: "Open workflow gaps",
    },
  ];
}
