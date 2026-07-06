// Typed client for the Aegis backend. Attaches the JWT access token, and on a
// 401 transparently refreshes once (via a shared in-flight promise so parallel
// requests don't stampede the refresh endpoint) before retrying.

import {
  clearTokens,
  getAccessToken,
  getRefreshToken,
  setTokens,
} from "./tokens";
import type {
  BillingSummary,
  GitHubAppInfo,
  GitHubRepo,
  GreyboxConfig,
  Installation,
  Repository,
  Scan,
  ScanFrequency,
  ScanMode,
  ScanReport,
  Schedule,
  SubscriptionTier,
  Token,
  User,
} from "./types";

const BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export class ApiError extends Error {
  status: number;
  /** Machine-readable code for gated actions, e.g. "no_subscription". */
  reason?: string;
  constructor(status: number, message: string, reason?: string) {
    super(message);
    this.status = status;
    this.reason = reason;
    this.name = "ApiError";
  }
}

/** Thrown when the session is unrecoverable and the user must sign in again. */
export class AuthExpiredError extends ApiError {
  constructor() {
    super(401, "Your session has expired. Please sign in again.");
    this.name = "AuthExpiredError";
  }
}

interface RequestOptions {
  method?: string;
  body?: unknown;
  auth?: boolean; // default true
  retry?: boolean; // internal: whether a refresh-retry is still allowed
}

let refreshInFlight: Promise<boolean> | null = null;

async function refreshAccessToken(): Promise<boolean> {
  const refresh_token = getRefreshToken();
  if (!refresh_token) return false;

  if (!refreshInFlight) {
    refreshInFlight = rawRequest<Token>("/auth/refresh", {
      method: "POST",
      body: { refresh_token },
      auth: false,
    })
      .then((token) => {
        setTokens(token);
        return true;
      })
      .catch(() => {
        clearTokens();
        return false;
      })
      .finally(() => {
        refreshInFlight = null;
      });
  }
  return refreshInFlight;
}

async function rawRequest<T>(path: string, opts: RequestOptions): Promise<T> {
  const headers: Record<string, string> = { Accept: "application/json" };
  if (opts.body !== undefined) headers["Content-Type"] = "application/json";
  if (opts.auth !== false) {
    const token = getAccessToken();
    if (token) headers["Authorization"] = `Bearer ${token}`;
  }

  const res = await fetch(`${BASE_URL}${path}`, {
    method: opts.method ?? "GET",
    headers,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
    cache: "no-store",
  });

  if (res.status === 204) return undefined as T;

  const isJson = res.headers.get("content-type")?.includes("application/json");
  const payload = isJson ? await res.json().catch(() => null) : await res.text();

  if (!res.ok) {
    // FastAPI's `detail` may be a string, or an object like
    // `{message, reason}` for gated (402) responses.
    let message = `Request failed (HTTP ${res.status})`;
    let reason: string | undefined;
    const detail = isJson && payload ? (payload as any).detail : payload;
    if (typeof detail === "string") {
      message = detail;
    } else if (detail && typeof detail === "object" && !Array.isArray(detail)) {
      if (typeof detail.message === "string") message = detail.message;
      if (typeof detail.reason === "string") reason = detail.reason;
    }
    throw new ApiError(res.status, message, reason);
  }

  return payload as T;
}

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  try {
    return await rawRequest<T>(path, opts);
  } catch (err) {
    const authed = opts.auth !== false;
    const canRetry = opts.retry !== false;
    if (err instanceof ApiError && err.status === 401 && authed && canRetry) {
      const ok = await refreshAccessToken();
      if (ok) return rawRequest<T>(path, { ...opts, retry: false });
      throw new AuthExpiredError();
    }
    throw err;
  }
}

async function rawBlob(path: string): Promise<Blob> {
  const headers: Record<string, string> = {};
  const token = getAccessToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${BASE_URL}${path}`, { headers, cache: "no-store" });
  if (!res.ok) throw new ApiError(res.status, `Download failed (HTTP ${res.status})`);
  return res.blob();
}

/** Authenticated binary fetch (e.g. PDF), with a single refresh-retry on 401. */
async function requestBlob(path: string): Promise<Blob> {
  try {
    return await rawBlob(path);
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      const ok = await refreshAccessToken();
      if (ok) return rawBlob(path);
      throw new AuthExpiredError();
    }
    throw err;
  }
}

export const api = {
  // --- Auth ---
  register: (email: string, password: string) =>
    request<Token>("/auth/register", {
      method: "POST",
      body: { email, password },
      auth: false,
    }),
  login: (email: string, password: string) =>
    request<Token>("/auth/login", {
      method: "POST",
      body: { email, password },
      auth: false,
    }),
  forgotPassword: (email: string) =>
    request<{ detail: string }>("/auth/forgot-password", {
      method: "POST",
      body: { email },
      auth: false,
    }),
  resetPassword: (token: string, new_password: string) =>
    request<Token>("/auth/reset-password", {
      method: "POST",
      body: { token, new_password },
      auth: false,
    }),
  verifyEmail: (token: string) =>
    request<{ detail: string }>("/auth/verify-email", {
      method: "POST",
      body: { token },
      auth: false,
    }),
  resendVerification: () =>
    request<{ detail: string }>("/auth/resend-verification", { method: "POST" }),
  githubAuth: (code: string, redirect_uri?: string, state?: string) =>
    request<Token>("/auth/github", {
      method: "POST",
      body: { code, redirect_uri, state },
      auth: false,
    }),

  // --- User ---
  me: () => request<User>("/users/me"),

  // --- Repositories ---
  listRepos: () => request<Repository[]>("/repos"),
  listAvailableRepos: () => request<GitHubRepo[]>("/repos/available"),
  syncRepo: (repo: { github_repo_id: string; name: string; url: string }) =>
    request<Repository>("/repos", { method: "POST", body: repo }),

  // --- Scans ---
  listScans: (repositoryId?: string) =>
    request<Scan[]>(
      repositoryId ? `/scans?repository_id=${encodeURIComponent(repositoryId)}` : "/scans"
    ),
  createScan: (body: {
    repository_id: string;
    scan_mode: ScanMode;
    custom_instructions?: string | null;
  }) => request<Scan>("/scans", { method: "POST", body }),
  getScan: (id: string) => request<Scan>(`/scans/${id}`),
  getReport: (id: string) => request<ScanReport>(`/scans/${id}/report`),
  getReportPdf: (id: string) => requestBlob(`/scans/${id}/report.pdf`),
  generateFixPr: (id: string) =>
    request<{ pull_request_url: string }>(`/scans/${id}/autofix`, { method: "POST" }),

  // --- Schedules ---
  listSchedules: () => request<Schedule[]>("/schedules"),
  createSchedule: (body: {
    repository_id: string;
    frequency: ScanFrequency;
    scan_mode: ScanMode;
    custom_instructions?: string | null;
  }) => request<Schedule>("/schedules", { method: "POST", body }),
  updateSchedule: (
    id: string,
    body: {
      frequency?: ScanFrequency;
      scan_mode?: ScanMode;
      custom_instructions?: string | null;
      enabled?: boolean;
    }
  ) => request<Schedule>(`/schedules/${id}`, { method: "PATCH", body }),
  deleteSchedule: (id: string) =>
    request<void>(`/schedules/${id}`, { method: "DELETE" }),

  // --- Grey-box (authenticated testing) ---
  getGreybox: (repoId: string) =>
    request<GreyboxConfig>(`/repos/${repoId}/greybox`),
  putGreybox: (
    repoId: string,
    body: {
      target_url: string;
      login_url?: string | null;
      username?: string | null;
      password?: string;
      extra?: string;
    }
  ) => request<GreyboxConfig>(`/repos/${repoId}/greybox`, { method: "PUT", body }),
  deleteGreybox: (repoId: string) =>
    request<void>(`/repos/${repoId}/greybox`, { method: "DELETE" }),

  // --- GitHub App ---
  getGitHubApp: () => request<GitHubAppInfo>("/github/app"),
  claimInstallation: (installation_id: string) =>
    request<Installation>("/github/installations", {
      method: "POST",
      body: { installation_id },
    }),
  deleteInstallation: (id: string) =>
    request<void>(`/github/installations/${id}`, { method: "DELETE" }),

  // --- Billing ---
  billingSummary: () => request<BillingSummary>("/billing/summary"),
  checkout: (tier: SubscriptionTier) =>
    request<{ checkout_url: string }>("/billing/checkout", {
      method: "POST",
      body: { tier },
    }),
  billingPortal: () =>
    request<{ portal_url: string }>("/billing/portal", { method: "POST" }),
};
