"use client";

import { useQuery } from "@tanstack/react-query";
import { GitBranch, Radar, ShieldAlert, Activity, Gauge } from "lucide-react";
import Link from "next/link";
import { useMemo } from "react";

import { NewScanAction } from "@/components/NewScanAction";
import {
  Card,
  EmptyState,
  ErrorState,
  PageHeader,
  SeverityBar,
  SeverityCountList,
  SkeletonCards,
  SkeletonList,
  StatusBadge,
} from "@/components/ui";
import { api } from "@/lib/api";
import { relativeTime, riskBand, riskScore } from "@/lib/format";
import type { DashboardSummary, Scan } from "@/lib/types";

export default function OverviewPage() {
  // One aggregate, computed server-side from the latest completed scan of each
  // repository. Summing every scan's report client-side used to count a
  // vulnerability once per re-scan, so a repo scanned ten times reported its
  // findings ten times over.
  const summaryQuery = useQuery({
    queryKey: ["dashboard", "summary"],
    queryFn: api.dashboardSummary,
  });
  const scansQuery = useQuery({ queryKey: ["scans"], queryFn: () => api.listScans() });
  const reposQuery = useQuery({ queryKey: ["repos"], queryFn: api.listRepos });

  const scans = scansQuery.data ?? [];
  const repos = reposQuery.data ?? [];
  const repoName = useMemo(() => new Map(repos.map((r) => [r.id, r.name])), [repos]);

  return (
    <>
      <PageHeader
        title="Overview"
        subtitle="Your continuous testing at a glance."
        action={<NewScanAction repositories={repos} />}
      />

      {summaryQuery.isLoading ? (
        <SkeletonCards />
      ) : summaryQuery.error || !summaryQuery.data ? (
        <ErrorState message="Could not load your security posture. Is the backend reachable?" />
      ) : (
        <Metrics summary={summaryQuery.data} />
      )}

      {/* Recent scans */}
      <section className="mt-10">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="font-display text-[15px] font-semibold text-fg">Recent scans</h2>
          {scans.length > 0 ? (
            <Link href="/scans" className="text-[12px] font-medium text-cyan-soft hover:text-cyan">
              View all
            </Link>
          ) : null}
        </div>

        {scansQuery.isLoading ? (
          <SkeletonList rows={4} />
        ) : scansQuery.error ? (
          <ErrorState message="Could not load your scans." />
        ) : scans.length === 0 ? (
          <EmptyState
            icon={Activity}
            title="No scans yet"
            action={<NewScanAction repositories={repos} label="Launch your first scan" />}
          >
            {repos.length > 0
              ? "Launch a pentest against one of your connected repositories."
              : "Connect a GitHub repository first, then launch your first pentest."}
          </EmptyState>
        ) : (
          <Card>
            <ul className="divide-y divide-line">
              {scans.slice(0, 6).map((scan) => (
                <RecentScanRow
                  key={scan.id}
                  scan={scan}
                  repoName={repoName.get(scan.repository_id)}
                />
              ))}
            </ul>
          </Card>
        )}
      </section>
    </>
  );
}

/* -------------------------------------------------------------------------- */
function Metrics({ summary }: { summary: DashboardSummary }) {
  const score = riskScore(summary.counts_by_severity);
  const band = riskBand(score);
  const { critical = 0, high = 0 } = summary.counts_by_severity ?? {};

  return (
    <>
      <div className="grid grid-cols-2 gap-3.5 lg:grid-cols-4">
        <Stat
          icon={ShieldAlert}
          label="Open findings"
          value={summary.open_findings}
          hint={`${critical} critical · ${high} high`}
          accent={critical > 0 ? "#FB5C6B" : undefined}
          href="/scans"
        />
        <Stat
          icon={Gauge}
          label="Risk score"
          value={score}
          hint={band.label}
          accent={band.color}
        />
        <Stat
          icon={Radar}
          label="Total scans"
          value={summary.total_scans}
          hint={
            summary.running_scans > 0
              ? `${summary.running_scans} in progress`
              : summary.last_scan_at
                ? `last ${relativeTime(summary.last_scan_at)}`
                : "none yet"
          }
          href="/scans"
        />
        <Stat
          icon={GitBranch}
          label="Repositories"
          value={summary.connected_repos}
          hint={`${summary.scanned_repos} scanned`}
          href="/repos"
        />
      </div>

      {/* The composition behind "open findings" — and a plain statement of what
          is being counted, since the number is not a sum over scan history. */}
      {summary.scanned_repos > 0 ? (
        <Card className="mt-3.5 space-y-2.5 px-5 py-4">
          <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1.5">
            <SeverityCountList
              counts={summary.counts_by_severity}
              emptyLabel="No open findings"
            />
            <p className="text-[11px] text-faint">
              Latest scan of {summary.scanned_repos}{" "}
              {summary.scanned_repos === 1 ? "repository" : "repositories"}
              {summary.suppressed_findings > 0
                ? ` · ${summary.suppressed_findings} triaged away`
                : ""}
            </p>
          </div>
          <SeverityBar counts={summary.counts_by_severity} />
        </Card>
      ) : null}
    </>
  );
}

function Stat({
  icon: Icon,
  label,
  value,
  hint,
  accent,
  href,
}: {
  icon: typeof Radar;
  label: string;
  value: number;
  hint?: string;
  accent?: string;
  href?: string;
}) {
  const body = (
    <>
      <div className="mb-3 flex items-center justify-between">
        <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-faint">
          {label}
        </span>
        <Icon className="h-4 w-4 text-faint" strokeWidth={1.75} />
      </div>
      <p
        className="font-display text-3xl font-bold text-fg"
        style={accent ? { color: accent } : undefined}
      >
        {value.toLocaleString()}
      </p>
      {hint ? <p className="mt-1 text-[11px] text-muted">{hint}</p> : null}
    </>
  );

  if (href) {
    return (
      <Card className="transition-colors hover:border-cyan/30">
        <Link href={href} className="block p-4">
          {body}
        </Link>
      </Card>
    );
  }
  return <Card className="p-4">{body}</Card>;
}

function RecentScanRow({ scan, repoName }: { scan: Scan; repoName?: string }) {
  return (
    <li>
      <Link
        href={`/scans/${scan.id}`}
        className="flex items-center gap-3 px-4 py-3.5 transition-colors hover:bg-surface/60"
      >
        <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-line bg-ink text-cyan-soft">
          <Radar className="h-4 w-4" strokeWidth={1.75} />
        </span>
        <div className="min-w-0 flex-1">
          <p className="truncate font-mono text-[13px] text-fg">{repoName ?? "Unknown repo"}</p>
          <p className="text-[11px] text-faint">
            {scan.scan_mode} scan · {relativeTime(scan.created_at)}
          </p>
        </div>
        {scan.counts_by_severity ? (
          <SeverityCountList
            counts={scan.counts_by_severity}
            emptyLabel="Clean"
            className="hidden sm:flex"
          />
        ) : null}
        <StatusBadge status={scan.status} />
      </Link>
    </li>
  );
}
