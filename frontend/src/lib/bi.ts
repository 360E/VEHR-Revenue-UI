import { getBrowserAccessToken } from "@/lib/auth";

export type ReportListItem = {
  report_key: string;
  name?: string;
};

export type EmbedConfigResponse = {
  type: "report" | "dashboard" | "tile";
  embedUrl: string;
  accessToken: string;
  reportId?: string;
  tokenExpiry?: string | null;
  expiresOn?: string | null;
};

function resolveApiBaseUrl(): string {
  const configuredBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (!configuredBaseUrl) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL is not configured.");
  }

  try {
    const parsed = new URL(configuredBaseUrl);
    return parsed.toString().replace(/\/$/, "");
  } catch {
    throw new Error("NEXT_PUBLIC_API_BASE_URL must be a valid absolute URL.");
  }
}

function describeErrorPayload(payload: unknown): string {
  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = (payload as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }
    if (Array.isArray(detail) && detail.length > 0) {
      return detail.map((item) => String(item)).join("; ");
    }
  }
  if (typeof payload === "string" && payload.trim()) {
    return payload;
  }
  return "Request failed.";
}

async function parseResponsePayload(response: Response): Promise<unknown> {
  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    return response.json().catch(() => null);
  }
  return response.text().catch(() => null);
}

async function requestJson<T>(url: string, failureLabel: string): Promise<T> {
  const headers = new Headers({ "Content-Type": "application/json" });
  const accessToken = getBrowserAccessToken();
  if (accessToken) {
    headers.set("Authorization", `Bearer ${accessToken}`);
  }

  const response = await fetch(url, {
    method: "GET",
    cache: "no-store",
    credentials: "include",
    headers,
  });
  const payload = await parseResponsePayload(response);

  if (!response.ok) {
    const detail = describeErrorPayload(payload);
    throw new Error(`${failureLabel} (${response.status}): ${detail}`);
  }
  return payload as T;
}

export async function fetchReports(): Promise<ReportListItem[]> {
  const requestUrl = `${resolveApiBaseUrl()}/api/v1/bi/reports`;
  const payload = await requestJson<unknown>(requestUrl, "Reports request failed");
  if (!Array.isArray(payload)) {
    throw new Error("Reports response was not an array.");
  }

  const reports: ReportListItem[] = [];
  for (const row of payload) {
    if (!row || typeof row !== "object") {
      continue;
    }
    const reportKeyRaw = (row as { report_key?: unknown; key?: unknown }).report_key
      ?? (row as { key?: unknown }).key;
    const reportKey = String(reportKeyRaw ?? "").trim();
    if (!reportKey) {
      continue;
    }
    const nameRaw = (row as { name?: unknown }).name;
    const name = typeof nameRaw === "string" && nameRaw.trim() ? nameRaw : undefined;
    reports.push({
      report_key: reportKey,
      ...(name ? { name } : {}),
    });
  }
  return reports;
}

export async function fetchEmbedConfig(reportKey: string): Promise<EmbedConfigResponse> {
  const requestUrl = `${resolveApiBaseUrl()}/api/v1/bi/embed-config?report_key=${encodeURIComponent(reportKey)}`;
  const payload = await requestJson<unknown>(requestUrl, "Embed config request failed");
  if (!payload || typeof payload !== "object") {
    throw new Error("Embed config response was not valid JSON.");
  }

  const reportIdRaw = (payload as { reportId?: unknown }).reportId;
  const embedUrl = String((payload as { embedUrl?: unknown }).embedUrl ?? "").trim();
  const embedAccessToken = String((payload as { accessToken?: unknown }).accessToken ?? "").trim();
  if (!embedUrl || !embedAccessToken) {
    throw new Error("Embed config response is missing required fields.");
  }

  const tokenExpiryRaw = (payload as { tokenExpiry?: unknown }).tokenExpiry;
  const expiresOnRaw = (payload as { expiresOn?: unknown }).expiresOn;
  const typeRaw = String((payload as { type?: unknown }).type ?? "report").toLowerCase();
  const type: "report" | "dashboard" | "tile" =
    typeRaw === "dashboard" || typeRaw === "tile" ? typeRaw : "report";

  return {
    type,
    reportId: typeof reportIdRaw === "string" && reportIdRaw.trim() ? reportIdRaw : undefined,
    embedUrl,
    accessToken: embedAccessToken,
    tokenExpiry: typeof tokenExpiryRaw === "string" && tokenExpiryRaw.trim() ? tokenExpiryRaw : null,
    expiresOn: typeof expiresOnRaw === "string" && expiresOnRaw.trim() ? expiresOnRaw : null,
  };
}
