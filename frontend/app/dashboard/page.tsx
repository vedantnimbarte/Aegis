import Link from "next/link";
import type { ComponentType } from "react";
import {
  Radar,
  ScanLine,
  ShieldAlert,
  ArrowUpRight,
  ArrowDownRight,
  ShieldCheck,
  GitPullRequestArrow,
  Play,
  CircleCheck,
  CircleX,
  Plug,
} from "lucide-react";
import {
  Card,
  Eyebrow,
  RiskGauge,
  btn,
  cx,
} from "@/components/aegis/kit";
import {
  dashboardStats,
  weeklyScans,
  recentActivity,
  type ActivityKind,
  type Severity,
} from "@/lib/mock-data";

const SEV_TEXT: Record<Severity, string> = {
  critical: "text-sev-critical",
  high: "text-sev-high",
  medium: "text-sev-medium",
  low: "text-sev-low",
};
const SEV_DOT: Record<Severity, string> = {
  critical: "bg-sev-critical",
  high: "bg-sev-high",
  medium: "bg-sev-medium",
  low: "bg-sev-low",
};

export default function DashboardHome() {
  const { totalScans, activeVulns, riskScore } = dashboardStats;
  const maxScans = Math.max(...weeklyScans.map((d) => d.scans));

  return (
    <>
      {/* Header */}
      <header className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <Eyebrow className="mb-2">Continuous coverage · 6 repositories</Eyebrow>
          <h1 className="font-display text-2xl font-semibold tracking-tight text-fg">
            Overview
          </h1>
          <p className="mt-1.5 text-sm text-muted">
            What Aegis has validated across your attack surface this week.
          </p>
        </div>
        <button className={btn.primary}>
          <Radar className="h-4 w-4" />
          Run scan
        </button>
      </header>

      {/* Stat cards */}
      <section className="grid gap-4 md:grid-cols-3">
        {/* Total scans */}
        <Card className="p-5">
          <div className="flex items-center justify-between">
            <Eyebrow>Total scans</Eyebrow>
            <ScanLine className="h-4 w-4 text-faint" />
          </div>
          <div className="mt-4 flex items-end gap-2.5">
            <span className="font-display text-4xl font-semibold text-fg">
              {totalScans.value}
            </span>
            <span className="mb-1.5 inline-flex items-center gap-0.5 font-mono text-xs text-signal">
              <ArrowUpRight className="h-3.5 w-3.5" />
              {totalScans.deltaPct}%
            </span>
          </div>
          <p className="mt-1 font-mono text-[11px] text-faint">{totalScans.sub}</p>
        </Card>

        {/* Active vulnerabilities */}
        <Card className="p-5">
          <div className="flex items-center justify-between">
            <Eyebrow>Active vulnerabilities</Eyebrow>
            <ShieldAlert className="h-4 w-4 text-faint" />
          </div>
          <div className="mt-4 flex items-end gap-2.5">
            <span className="font-display text-4xl font-semibold text-fg">
              {activeVulns.value}
            </span>
            <span className="mb-1.5 font-mono text-[11px] text-faint">validated · open</span>
          </div>
          <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1.5">
            {(Object.keys(activeVulns.breakdown) as Severity[]).map((k) => (
              <span
                key={k}
                className="inline-flex items-center gap-1.5 font-mono text-xs text-muted"
              >
                <span className={cx("h-1.5 w-1.5 rounded-full", SEV_DOT[k])} />
                <span className={cx("font-semibold", SEV_TEXT[k])}>
                  {activeVulns.breakdown[k]}
                </span>
                <span className="capitalize text-faint">{k}</span>
              </span>
            ))}
          </div>
        </Card>

        {/* Average risk score — the signature gauge */}
        <Card className="flex items-center gap-4 p-5">
          <RiskGauge score={riskScore.value} size={120} />
          <div>
            <Eyebrow>Average risk score</Eyebrow>
            <div className="mt-3 inline-flex items-center gap-1 font-mono text-xs text-signal">
              <ArrowDownRight className="h-3.5 w-3.5" />
              {Math.abs(riskScore.delta)} pts
            </div>
            <p className="mt-1 font-mono text-[11px] text-faint">
              {riskScore.sub} vs. last week
            </p>
          </div>
        </Card>
      </section>

      {/* Chart + severity mix */}
      <section className="mt-4 grid gap-4 lg:grid-cols-3">
        {/* Scans over last 7 days */}
        <Card className="p-5 lg:col-span-2">
          <div className="flex items-center justify-between">
            <div>
              <Eyebrow>Last 7 days</Eyebrow>
              <h2 className="mt-1.5 font-display text-base font-semibold text-fg">
                Scans &amp; validated findings
              </h2>
            </div>
            <div className="flex items-center gap-4 font-mono text-[11px] text-faint">
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-sm bg-violet" />
                scans
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-sm bg-cyan" />
                validated
              </span>
            </div>
          </div>

          <div className="mt-7 flex h-44 items-end justify-between gap-2.5 sm:gap-4">
            {weeklyScans.map((d) => (
              <div key={d.day} className="group flex flex-1 flex-col items-center gap-2.5">
                <div className="relative flex h-full w-full items-end justify-center gap-1">
                  <div
                    className="w-full max-w-[16px] rounded-t bg-gradient-to-t from-violet/25 to-violet transition-opacity group-hover:from-violet/40"
                    style={{ height: `${Math.max(6, (d.scans / maxScans) * 100)}%` }}
                    title={`${d.scans} scans`}
                  />
                  <div
                    className="w-full max-w-[16px] rounded-t bg-gradient-to-t from-cyan/20 to-cyan/80"
                    style={{ height: `${Math.max(4, (d.validated / maxScans) * 100)}%` }}
                    title={`${d.validated} validated`}
                  />
                </div>
                <span className="font-mono text-[11px] text-faint">{d.day}</span>
              </div>
            ))}
          </div>
        </Card>

        {/* Findings by severity */}
        <Card className="p-5">
          <Eyebrow>Open findings by severity</Eyebrow>
          <div className="mt-5 space-y-4">
            {(Object.keys(activeVulns.breakdown) as Severity[]).map((k) => {
              const total = activeVulns.value;
              const n = activeVulns.breakdown[k];
              return (
                <div key={k}>
                  <div className="mb-1.5 flex items-center justify-between font-mono text-xs">
                    <span className="capitalize text-muted">{k}</span>
                    <span className={cx("font-semibold", SEV_TEXT[k])}>{n}</span>
                  </div>
                  <div className="h-1.5 overflow-hidden rounded-full bg-raised">
                    <div
                      className={cx("h-full rounded-full", SEV_DOT[k])}
                      style={{ width: `${(n / total) * 100}%` }}
                    />
                  </div>
                </div>
              );
            })}
          </div>
        </Card>
      </section>

      {/* Recent activity */}
      <section className="mt-4">
        <Card className="p-5">
          <div className="flex items-center justify-between">
            <div>
              <Eyebrow>Live feed</Eyebrow>
              <h2 className="mt-1.5 font-display text-base font-semibold text-fg">
                Recent activity
              </h2>
            </div>
            <Link
              href="/dashboard/scans"
              className="font-mono text-xs text-muted transition-colors hover:text-violet-soft"
            >
              View all scans →
            </Link>
          </div>

          <ul className="mt-5 divide-y divide-line">
            {recentActivity.map((a) => (
              <ActivityRow key={a.id} {...a} />
            ))}
          </ul>
        </Card>
      </section>
    </>
  );
}

const ACTIVITY_META: Record<
  ActivityKind,
  { icon: ComponentType<{ className?: string }>; ring: string; text: string }
> = {
  validated: { icon: ShieldCheck, ring: "border-signal/30 bg-signal/10", text: "text-signal" },
  remediation: {
    icon: GitPullRequestArrow,
    ring: "border-violet/30 bg-violet/10",
    text: "text-violet-soft",
  },
  scan_started: { icon: Play, ring: "border-cyan/30 bg-cyan/10", text: "text-cyan" },
  scan_completed: {
    icon: CircleCheck,
    ring: "border-line bg-raised",
    text: "text-muted",
  },
  scan_failed: { icon: CircleX, ring: "border-danger/30 bg-danger/10", text: "text-danger" },
  repo_connected: { icon: Plug, ring: "border-line bg-raised", text: "text-muted" },
};

function ActivityRow({
  kind,
  repo,
  detail,
  time,
  severity,
}: (typeof recentActivity)[number]) {
  const meta = ACTIVITY_META[kind];
  const Icon = meta.icon;
  return (
    <li className="flex items-start gap-3.5 py-3.5 first:pt-0 last:pb-0">
      <span
        className={cx(
          "mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-lg border",
          meta.ring,
          meta.text,
        )}
      >
        <Icon className="h-4 w-4" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
          <span className="font-mono text-xs text-violet-soft">{repo}</span>
          {severity && (
            <span
              className={cx(
                "font-mono text-[10px] uppercase tracking-wider",
                SEV_TEXT[severity],
              )}
            >
              {severity}
            </span>
          )}
        </div>
        <p className="mt-0.5 truncate text-sm text-muted">{detail}</p>
      </div>
      <span className="shrink-0 font-mono text-[11px] text-faint">{time}</span>
    </li>
  );
}
