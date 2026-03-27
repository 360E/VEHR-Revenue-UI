import { z } from "zod";

import { apiClientFetch } from "@/lib/api/client";
import { isFetchFailedMessage } from "@/lib/error-messages";

export const REVENUE_WORKLIST_API_PATH = "/api/revenue/worklist";
export const REVENUE_WORKLIST_ACTIONS_API_PATH = "/api/revenue/worklist/actions";
export const REVENUE_WORKLIST_ITEM_API_PATH = "/api/revenue/worklist";

const worklistRecommendedActionSchema = z.object({
  type: z.string().min(1),
  confidence: z.string().min(1),
  reason: z.string().min(1),
  rationale: z.string().nullable().optional(),
  decision_drivers: z.array(z.string()).default([]),
  urgency_cues: z.array(z.string()).default([]),
  impact_cues: z.array(z.string()).default([]),
  escalation_signals: z.array(z.string()).default([]),
});

const worklistShadowEvaluationSchema = z.object({
  decision: z.string().min(1),
  candidate_action: z.string().nullable().optional(),
  reason_code: z.string().min(1),
  explanation: z.string().min(1),
  policy_name: z.string().min(1),
});

const worklistSupervisionSchema = z.object({
  state: z.string().min(1),
  policy_name: z.string().min(1),
  candidate_action: z.string().nullable().optional(),
  reason_code: z.string().min(1),
  explanation: z.string().min(1),
  approval_request_id: z.string().nullable().optional(),
  requested_at: z.string().nullable().optional(),
  decided_at: z.string().nullable().optional(),
  requested_by_user_id: z.string().nullable().optional(),
  decided_by_user_id: z.string().nullable().optional(),
  execution_audit_id: z.string().nullable().optional(),
});

const worklistTimelineEntrySchema = z.object({
  at: z.string().min(1),
  event: z.string().min(1),
  detail: z.string().min(1),
});

const worklistAssigneeSchema = z.object({
  user_id: z.string().nullable().optional(),
  user_name: z.string().nullable().optional(),
  team_id: z.string().nullable().optional(),
  team_label: z.string().nullable().optional(),
});

const worklistItemSchema = z.object({
  id: z.string().min(1),
  type: z.string().min(1),
  status: z.string().min(1),
  title: z.string().min(1),
  reason: z.string().min(1),
  subtitle: z.string().nullable().optional(),
  claim_id: z.string().nullable().optional(),
  claim_ref: z.string().nullable().optional(),
  patient_id: z.string().nullable().optional(),
  patient_name: z.string().nullable().optional(),
  payer: z.string().nullable().optional(),
  facility: z.string().nullable().optional(),
  amount_at_risk: z.string().min(1),
  amount_at_risk_cents: z.number(),
  aging_days: z.number().nullable().optional(),
  aging_bucket: z.string().min(1),
  priority: z.string().min(1),
  sla_state: z.string().min(1),
  escalation_state: z.string().min(1),
  reason_codes: z.array(z.string()),
  recommended_action: worklistRecommendedActionSchema,
  shadow_evaluation: worklistShadowEvaluationSchema,
  supervision: worklistSupervisionSchema,
  allowed_actions: z.array(z.string()),
  assignee: worklistAssigneeSchema,
  updated_at: z.string().min(1),
  created_at: z.string().min(1),
  timeline_summary: z.array(worklistTimelineEntrySchema),
});

const worklistSummarySchema = z.object({
  total: z.number(),
  priority_counts: z.record(z.string(), z.number()),
  status_counts: z.record(z.string(), z.number()).default({}),
  type_counts: z.record(z.string(), z.number()).default({}),
  needs_review_count: z.number().default(0),
  total_amount_at_risk_cents: z.number().default(0),
});

const worklistProjectionHealthSchema = z.object({
  pending_refresh_event_count: z.number().default(0),
  retry_refresh_event_count: z.number().default(0),
  oldest_queued_refresh_event_at: z.string().nullable().optional(),
  projection_may_be_stale: z.boolean().default(false),
});

export const revenueWorklistPageSchema = z.object({
  items: z.array(worklistItemSchema),
  total: z.number(),
  page: z.number(),
  page_size: z.number(),
  total_pages: z.number(),
  sort_by: z.string().min(1),
  sort_direction: z.string().min(1),
  summary: worklistSummarySchema,
  projection_health: worklistProjectionHealthSchema,
});

const worklistActionResponseSchema = z.object({
  action: z.string().min(1),
  updated_work_item_ids: z.array(z.string()),
  updated_count: z.number(),
  failed_count: z.number().default(0),
  results: z
    .array(
      z.object({
        work_item_id: z.string().min(1),
        action: z.string().min(1),
        status: z.string().min(1),
        audit_id: z.string().nullable().optional(),
        error_message: z.string().nullable().optional(),
        result_payload: z.record(z.string(), z.unknown()).nullable().optional(),
      }),
    )
    .default([]),
});

const worklistHistoryEntrySchema = z.object({
  id: z.string().min(1),
  work_item_id: z.string().min(1),
  entry_type: z.string().min(1),
  action_type: z.string().min(1),
  status: z.string().min(1),
  performed_by_user_id: z.string().nullable().optional(),
  performed_by_user_name: z.string().nullable().optional(),
  policy_name: z.string().nullable().optional(),
  approval_request_id: z.string().nullable().optional(),
  input_payload: z.record(z.string(), z.unknown()).default({}),
  result_payload: z.record(z.string(), z.unknown()).nullable().optional(),
  error_message: z.string().nullable().optional(),
  created_at: z.string().min(1),
  completed_at: z.string().nullable().optional(),
});

const worklistApprovalActionResponseSchema = z.object({
  work_item_id: z.string().min(1),
  state: z.string().min(1),
  policy_name: z.string().min(1),
  candidate_action: z.string().nullable().optional(),
  reason_code: z.string().min(1),
  explanation: z.string().min(1),
  approval_request_id: z.string().nullable().optional(),
  execution_audit_id: z.string().nullable().optional(),
  executed: z.boolean().default(false),
  result_payload: z.record(z.string(), z.unknown()).nullable().optional(),
});

export type RevenueWorklistPage = z.infer<typeof revenueWorklistPageSchema>;
export type RevenueWorklistItem = z.infer<typeof worklistItemSchema>;
export type RevenueWorklistActionResponse = z.infer<typeof worklistActionResponseSchema>;
export type RevenueWorklistHistoryEntry = z.infer<typeof worklistHistoryEntrySchema>;
export type RevenueWorklistApprovalActionResponse = z.infer<typeof worklistApprovalActionResponseSchema>;

function buildQuery(params?: Record<string, string | number | null | undefined>): string {
  if (!params) {
    return "";
  }

  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === null || typeof value === "undefined" || value === "") {
      return;
    }
    searchParams.set(key, String(value));
  });

  const query = searchParams.toString();
  return query ? `?${query}` : "";
}

function formatWorklistError(status: number, payload: unknown, text: string): string {
  if (payload && typeof payload === "object" && !Array.isArray(payload)) {
    const detail = "detail" in payload ? payload.detail : null;
    const error = "error" in payload ? payload.error : null;
    if (typeof error === "string" && error.trim()) {
      return error.trim();
    }
    if (typeof detail === "string" && detail.trim()) {
      return detail.trim();
    }
  }

  if (typeof payload === "string" && payload.trim()) {
    return isFetchFailedMessage(payload) ? "Unable to reach the VEHR worklist endpoint right now." : payload.trim();
  }

  if (text.trim()) {
    return text.trim();
  }

  return `Unable to load the worklist (status ${status}).`;
}

export async function fetchRevenueWorklist(params?: Record<string, string | number | null | undefined>): Promise<RevenueWorklistPage> {
  const response = await apiClientFetch(`${REVENUE_WORKLIST_API_PATH}${buildQuery(params)}`);

  if (!response.ok) {
    throw new Error(formatWorklistError(response.status, response.data, response.text));
  }

  return revenueWorklistPageSchema.parse(response.data);
}

export async function runRevenueWorklistAction(payload: {
  workItemIds: string[];
  action: "assign" | "reassign" | "mark_in_progress";
  assignedToUserId?: string | null;
  assignedTeamId?: string | null;
}): Promise<RevenueWorklistActionResponse> {
  const response = await apiClientFetch(REVENUE_WORKLIST_ACTIONS_API_PATH, {
    method: "POST",
    headers: {
      "content-type": "application/json",
    },
    body: JSON.stringify({
      work_item_ids: payload.workItemIds,
      action: payload.action,
      assigned_to_user_id: payload.assignedToUserId ?? null,
      assigned_team_id: payload.assignedTeamId ?? null,
    }),
  });

  if (!response.ok) {
    throw new Error(formatWorklistError(response.status, response.data, response.text));
  }

  return worklistActionResponseSchema.parse(response.data);
}

export async function fetchRevenueWorklistHistory(workItemId: string): Promise<RevenueWorklistHistoryEntry[]> {
  const response = await apiClientFetch(`${REVENUE_WORKLIST_ITEM_API_PATH}/${workItemId}/history`);

  if (!response.ok) {
    throw new Error(formatWorklistError(response.status, response.data, response.text));
  }

  return z.array(worklistHistoryEntrySchema).parse(response.data);
}

async function postApprovalAction(
  workItemId: string,
  actionPath: "approval-request" | "approval-approve" | "approval-reject",
): Promise<RevenueWorklistApprovalActionResponse> {
  const response = await apiClientFetch(`${REVENUE_WORKLIST_ITEM_API_PATH}/${workItemId}/${actionPath}`, {
    method: "POST",
    headers: {
      "content-type": "application/json",
    },
  });

  if (!response.ok) {
    throw new Error(formatWorklistError(response.status, response.data, response.text));
  }

  return worklistApprovalActionResponseSchema.parse(response.data);
}

export function requestRevenueWorklistApproval(workItemId: string): Promise<RevenueWorklistApprovalActionResponse> {
  return postApprovalAction(workItemId, "approval-request");
}

export function approveRevenueWorklistApproval(workItemId: string): Promise<RevenueWorklistApprovalActionResponse> {
  return postApprovalAction(workItemId, "approval-approve");
}

export function rejectRevenueWorklistApproval(workItemId: string): Promise<RevenueWorklistApprovalActionResponse> {
  return postApprovalAction(workItemId, "approval-reject");
}
