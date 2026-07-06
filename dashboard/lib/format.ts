// Presentation helpers: severity/status styling, dates, risk scoring, and the
// GitHub OAuth authorize URL.

import type { ScanStatus, Severity } from "./types";

export const SEVERITY_ORDER: Severity[] = ["critical", "high", "medium", "low", "info"];

interface Tone {
  label: string;
  /** Tailwind classes for a bordered pill. */
  pill: string;
  /** Hex dot / accent color. */
  dot: string;
}

export const SEVERITY_META: Record<Severity, Tone> = {
  critical: { label: "Critical", pill: "border-danger/30 bg-danger/10 text-danger", dot: "#FB5C6B" },
  high: { label: "High", pill: "border-amber/30 bg-amber/10 text-amber", dot: "#F5B451" },
  medium: { label: "Medium", pill: "border-violet/30 bg-violet/10 text-violet", dot: "#A78BFA" },
  low: { label: "Low", pill: "border-cyan/30 bg-cyan/10 text-cyan-soft", dot: "#67E8F9" },
  info: { label: "Info", pill: "border-line bg-surface text-muted", dot: "#8A93A6" },
};

export const STATUS_META: Record<ScanStatus, Tone> = {
  pending: { label: "Pending", pill: "border-line bg-surface text-muted", dot: "#8A93A6" },
  running: { label: "Running", pill: "border-cyan/30 bg-cyan/10 text-cyan-soft", dot: "#22D3EE" },
  completed: { label: "Completed", pill: "border-signal/30 bg-signal/10 text-signal", dot: "#4ADE80" },
  failed: { label: "Failed", pill: "border-danger/30 bg-danger/10 text-danger", dot: "#FB5C6B" },
};

/** Weighted contribution of each severity to a 0–100 risk score. */
const RISK_WEIGHTS: Record<Severity, number> = {
  critical: 40,
  high: 20,
  medium: 8,
  low: 3,
  info: 0,
};

/**
 * A coarse 0–100 risk score for a set of findings. Saturating so a handful of
 * criticals pins it near 100 without unbounded growth.
 */
export function riskScore(counts: Partial<Record<Severity, number>>): number {
  let raw = 0;
  for (const sev of SEVERITY_ORDER) raw += (counts[sev] ?? 0) * RISK_WEIGHTS[sev];
  if (raw <= 0) return 0;
  // Diminishing returns curve, capped at 100.
  return Math.min(100, Math.round(100 * (1 - Math.exp(-raw / 100))));
}

export function riskBand(score: number): { label: string; color: string } {
  if (score >= 75) return { label: "Critical", color: "#FB5C6B" };
  if (score >= 50) return { label: "High", color: "#F5B451" };
  if (score >= 25) return { label: "Elevated", color: "#A78BFA" };
  if (score > 0) return { label: "Low", color: "#67E8F9" };
  return { label: "Clean", color: "#4ADE80" };
}

export function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function relativeTime(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso).getTime();
  if (Number.isNaN(d)) return "—";
  const diff = Date.now() - d;
  const mins = Math.round(diff / 60000);
  if (mins < 1) return "just now";
  if (mins < 60) return `${mins}m ago`;
  const hrs = Math.round(mins / 60);
  if (hrs < 24) return `${hrs}h ago`;
  const days = Math.round(hrs / 24);
  if (days < 30) return `${days}d ago`;
  return formatDate(iso);
}

export function formatDuration(startIso: string | null, endIso: string | null): string {
  if (!startIso || !endIso) return "—";
  const ms = new Date(endIso).getTime() - new Date(startIso).getTime();
  if (Number.isNaN(ms) || ms < 0) return "—";
  const secs = Math.round(ms / 1000);
  if (secs < 60) return `${secs}s`;
  const mins = Math.floor(secs / 60);
  const rem = secs % 60;
  if (mins < 60) return rem ? `${mins}m ${rem}s` : `${mins}m`;
  const hrs = Math.floor(mins / 60);
  return `${hrs}h ${mins % 60}m`;
}

/** Build the GitHub OAuth authorize URL, stashing a CSRF `state` for later. */
export function buildGitHubAuthUrl(): string {
  const clientId = process.env.NEXT_PUBLIC_GITHUB_CLIENT_ID ?? "";
  const redirectUri =
    process.env.NEXT_PUBLIC_GITHUB_REDIRECT_URI ??
    (typeof window !== "undefined" ? `${window.location.origin}/auth/callback` : "");

  const state = cryptoRandom();
  if (typeof window !== "undefined") {
    window.sessionStorage.setItem("aegis.oauth_state", state);
  }

  const params = new URLSearchParams({
    client_id: clientId,
    redirect_uri: redirectUri,
    scope: "repo read:user user:email",
    state,
    allow_signup: "true",
  });
  return `https://github.com/login/oauth/authorize?${params.toString()}`;
}

function cryptoRandom(): string {
  if (typeof window !== "undefined" && window.crypto?.randomUUID) {
    return window.crypto.randomUUID();
  }
  return Math.random().toString(36).slice(2);
}
