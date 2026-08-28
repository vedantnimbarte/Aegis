// Transport for the Aegis API: attaches the JWT access token and the active
// organization header, and on a 401 transparently refreshes once (via a shared
// in-flight promise so parallel requests don't stampede the refresh endpoint)
// before retrying.
//
// The endpoint methods live in ./api-endpoints; ./api re-exports both.

import {
  clearTokens,
  getAccessToken,
  getRefreshToken,
  setTokens,
} from "./tokens";
import { getActiveOrg } from "./org";
import type { Token } from "./types";

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
    // Absent, the API acts in the user's own organization — so this header
    // only appears once someone has actually switched.
    const org = getActiveOrg();
    if (org) headers["X-Aegis-Org"] = org;
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

export async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
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
  const org = getActiveOrg();
  if (org) headers["X-Aegis-Org"] = org;
  const res = await fetch(`${BASE_URL}${path}`, { headers, cache: "no-store" });
  if (!res.ok) throw new ApiError(res.status, `Download failed (HTTP ${res.status})`);
  return res.blob();
}

/** Authenticated binary fetch (e.g. PDF), with a single refresh-retry on 401. */
export async function requestBlob(path: string): Promise<Blob> {
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
