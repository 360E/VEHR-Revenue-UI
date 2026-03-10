import { ZodError } from "zod";

import { apiClientFetch, logApiFailure } from "@/lib/api/client";
import {
  apiErrorResponseSchema,
  revenueSnapshotMissingSchema,
  revenueSnapshotResponseSchema,
  type JsonValue,
  type RevenueSnapshotResponse,
} from "@/lib/api/types";
import { isFetchFailedMessage } from "@/lib/error-messages";

export const LATEST_REVENUE_SNAPSHOT_BACKEND_PATH = "/api/v1/revenue/snapshots/latest";
export const LATEST_REVENUE_SNAPSHOT_API_PATH = "/api/dashboard";
export const DASHBOARD_PENDING_RETRY_INTERVAL_MS = 15_000;
export const DASHBOARD_RECOVERABLE_RETRY_INTERVAL_MS = 20_000;
export const DASHBOARD_PENDING_RETRY_LIMIT = 8;
export const DASHBOARD_RECOVERABLE_RETRY_LIMIT = 4;

type DashboardRetryPolicy = {
  intervalMs: number;
  maxAttempts: number;
};

export type DashboardState =
  | { status: "loading" }
  | { status: "pending"; message: string; detail?: string; retryPolicy: DashboardRetryPolicy }
  | { status: "recoverable"; message: string; detail?: string; code?: number; retryPolicy: DashboardRetryPolicy }
  | { status: "ready"; snapshot: RevenueSnapshotResponse }
  | { status: "backend_failure"; message: string; detail?: string; code?: number }
  | { status: "fatal"; message: string; detail?: string; code?: number }
  | { status: "unauthorized"; message: string; detail?: string; code: 401 | 403 };

type DashboardProblem = {
  code?: string;
  message: string;
  detail?: string;
};

const PENDING_RETRY_POLICY: DashboardRetryPolicy = {
  intervalMs: DASHBOARD_PENDING_RETRY_INTERVAL_MS,
  maxAttempts: DASHBOARD_PENDING_RETRY_LIMIT,
};

const RECOVERABLE_RETRY_POLICY: DashboardRetryPolicy = {
  intervalMs: DASHBOARD_RECOVERABLE_RETRY_INTERVAL_MS,
  maxAttempts: DASHBOARD_RECOVERABLE_RETRY_LIMIT,
};

const PENDING_GENERATION_HINTS = ["generating", "generation", "building", "preparing", "retry", "recovering", "pending"];
const UNAUTHORIZED_HINTS = ["invalid token", "invalid_token", "unauthorized", "forbidden", "session expired"];

function normalizeErrorMessage(message: string, fallback: string): string {
  const trimmedMessage = message.trim();

  if (!trimmedMessage) {
    return fallback;
  }

  return isFetchFailedMessage(trimmedMessage) ? fallback : trimmedMessage;
}

function truncateText(value: string, maxLength = 240): string {
  return value.length <= maxLength ? value : `${value.slice(0, maxLength)}…`;
}

function humanizeProblemCode(code: string): string {
  return code
    .replace(/[_-]+/g, " ")
    .replace(/\s+/g, " ")
    .trim()
    .replace(/^\w/, (character) => character.toUpperCase());
}

function normalizeProblemCode(value: string | undefined): string | undefined {
  const trimmedValue = value?.trim().toLowerCase();

  if (!trimmedValue) {
    return undefined;
  }

  return trimmedValue.replace(/\s+/g, "_");
}

function getProblemMessageForCode(code: string | undefined, fallback: string): string {
  switch (code) {
    case "snapshot_not_found":
      return "The latest revenue snapshot is not ready yet.";
    case "snapshot_generation_failed":
      return "The revenue snapshot could not be generated.";
    case "invalid_token":
    case "unauthorized":
    case "forbidden":
      return "Your session has expired. Sign in again to continue.";
    default:
      return fallback;
  }
}

function summarizeJsonValue(value: JsonValue | undefined, depth = 0): string | undefined {
  if (value === null || typeof value === "undefined") {
    return undefined;
  }

  if (typeof value === "string") {
    const normalized = value.replace(/\s+/g, " ").trim();
    return normalized ? truncateText(normalized) : undefined;
  }

  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }

  if (Array.isArray(value)) {
    const summarizedItems = value
      .map((item) => summarizeJsonValue(item, depth + 1))
      .filter((item): item is string => Boolean(item))
      .slice(0, 3);

    if (summarizedItems.length === 0) {
      return undefined;
    }

    const suffix = value.length > summarizedItems.length ? " …" : "";
    return truncateText(summarizedItems.join("; ") + suffix);
  }

  const summarizedEntries = Object.entries(value)
    .map(([key, entryValue]) => {
      const summarizedEntryValue = summarizeJsonValue(entryValue, depth + 1);

      if (!summarizedEntryValue) {
        return null;
      }

      return depth === 0 ? `${humanizeProblemCode(key)}: ${summarizedEntryValue}` : summarizedEntryValue;
    })
    .filter((entry): entry is string => Boolean(entry))
    .slice(0, 3);

  if (summarizedEntries.length === 0) {
    return undefined;
  }

  const suffix = Object.keys(value).length > summarizedEntries.length ? " …" : "";
  return truncateText(summarizedEntries.join("; ") + suffix);
}

function hasPendingGenerationHint(problem: DashboardProblem): boolean {
  const combinedText = [problem.message, problem.detail, problem.code]
    .filter((value): value is string => Boolean(value))
    .join(" ")
    .toLowerCase();

  return PENDING_GENERATION_HINTS.some((hint) => combinedText.includes(hint));
}

function isUnauthorizedProblem(problem: DashboardProblem, status: number): status is 401 | 403 {
  if (status === 401 || status === 403) {
    return true;
  }

  const combinedText = [problem.code, problem.message, problem.detail]
    .filter((value): value is string => Boolean(value))
    .join(" ")
    .toLowerCase();

  return UNAUTHORIZED_HINTS.some((hint) => combinedText.includes(hint));
}

function isRecoverableStatus(status: number): boolean {
  return [408, 425, 429, 500, 502, 503, 504].includes(status);
}

function isBackendFailureProblem(problem: DashboardProblem): boolean {
  return problem.code === "snapshot_generation_failed" || problem.code?.endsWith("_failed") === true;
}

function getApiProblem(payload: unknown, text: string, fallback: string): DashboardProblem {
  const parsedError = apiErrorResponseSchema.safeParse(payload);

  if (parsedError.success) {
    const code = normalizeProblemCode(parsedError.data.error);
    const detail = summarizeJsonValue(parsedError.data.detail);
    const explicitMessage = normalizeErrorMessage(parsedError.data.message ?? "", "");
    const fallbackMessage = getProblemMessageForCode(code, fallback);
    const message = explicitMessage || (code ? fallbackMessage : detail || fallbackMessage);

    return {
      code,
      message,
      detail: detail && detail !== message ? detail : undefined,
    };
  }

  if (payload && typeof payload === "object" && !Array.isArray(payload)) {
    const record = payload as Record<string, unknown>;
    const message = [record.error, record.detail, record.message].find(
      (value): value is string => typeof value === "string" && value.trim().length > 0,
    );

    if (message) {
      return {
        message: normalizeErrorMessage(message, fallback),
      };
    }
  }

  const normalizedText = normalizeErrorMessage(text, fallback);

  return {
    message: normalizedText,
  };
}

function getSchemaError(error: ZodError, fallback: string): DashboardProblem {
  return {
    message: fallback,
    detail: error.issues.map((issue) => issue.message).join("; "),
  };
}

export async function fetchLatestRevenueSnapshotState(): Promise<Exclude<DashboardState, { status: "loading" }>> {
  try {
    const response = await apiClientFetch(LATEST_REVENUE_SNAPSHOT_API_PATH);

    if (response.ok) {
      const parsedSnapshot = revenueSnapshotResponseSchema.safeParse(response.data);

      if (parsedSnapshot.success) {
        return {
          status: "ready",
          snapshot: parsedSnapshot.data,
        };
      }

      const detail = getSchemaError(parsedSnapshot.error, "Revenue snapshot data did not match the expected contract.");
      logApiFailure({
        route: LATEST_REVENUE_SNAPSHOT_API_PATH,
        status: response.status,
        reason: detail.message,
        detail: detail.detail,
      });

      return {
        status: "fatal",
        message: detail.message,
        detail: detail.detail,
        code: response.status,
      };
    }

    if (response.status === 404) {
      const parsedMissing = revenueSnapshotMissingSchema.safeParse(response.data);

      if (parsedMissing.success) {
        const detail =
          summarizeJsonValue(parsedMissing.data.detail) ??
          normalizeErrorMessage(parsedMissing.data.message ?? "", "No revenue snapshot is available yet.");

        logApiFailure({
          route: LATEST_REVENUE_SNAPSHOT_API_PATH,
          status: response.status,
          reason: parsedMissing.data.error,
          detail,
        });

        if (hasPendingGenerationHint({ code: parsedMissing.data.error, message: detail, detail })) {
          return {
            status: "pending",
            message: "The first revenue snapshot is being prepared.",
            detail,
            retryPolicy: PENDING_RETRY_POLICY,
          };
        }

        return {
          status: "recoverable",
          message: "No revenue snapshot is available yet.",
          detail,
          code: response.status,
          retryPolicy: RECOVERABLE_RETRY_POLICY,
        };
      }
    }

    const fallbackError =
      response.status === 401 || response.status === 403
        ? "Your session has expired. Sign in again to continue."
        : `Unable to load dashboard data (status ${response.status}).`;
    const problem = getApiProblem(response.data, response.text, fallbackError);

    logApiFailure({
      route: LATEST_REVENUE_SNAPSHOT_API_PATH,
      status: response.status,
      reason: problem.message,
      detail: problem.detail,
    });

    if (isUnauthorizedProblem(problem, response.status)) {
      return {
        status: "unauthorized",
        message: "Your session has expired. Sign in again to continue.",
        detail: problem.detail ?? problem.message,
        code: response.status === 403 ? 403 : 401,
      };
    }

    if (isBackendFailureProblem(problem)) {
      return {
        status: "backend_failure",
        message: problem.message,
        detail: problem.detail,
        code: response.status,
      };
    }

    if (problem.code === "snapshot_not_found") {
      return hasPendingGenerationHint(problem)
        ? {
            status: "pending",
            message: "The latest revenue snapshot is still being generated.",
            detail: problem.detail ?? problem.message,
            retryPolicy: PENDING_RETRY_POLICY,
          }
        : {
            status: "recoverable",
            message: "The revenue snapshot is temporarily unavailable.",
            detail: problem.detail ?? problem.message,
            code: response.status,
            retryPolicy: RECOVERABLE_RETRY_POLICY,
          };
    }

    if (isRecoverableStatus(response.status)) {
      return {
        status: "recoverable",
        message: "The dashboard is waiting for the backend to recover.",
        detail: problem.detail ?? problem.message,
        code: response.status,
        retryPolicy: RECOVERABLE_RETRY_POLICY,
      };
    }

    return {
      status: "fatal",
      message: problem.message,
      detail: problem.detail,
      code: response.status,
    };
  } catch (error) {
    const message =
      error instanceof Error
        ? normalizeErrorMessage(error.message, "Unable to load dashboard data right now.")
        : "Unable to load dashboard data right now.";

    logApiFailure({
      route: LATEST_REVENUE_SNAPSHOT_API_PATH,
      reason: message,
    });

    return {
      status: "recoverable",
      message: "The dashboard is waiting for the backend to recover.",
      detail: message,
      retryPolicy: RECOVERABLE_RETRY_POLICY,
    };
  }
}
