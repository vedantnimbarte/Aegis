"use client";

import { useQueries, useQuery } from "@tanstack/react-query";
import { GitBranch, Radar, ShieldAlert, Activity, Gauge, Plus } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { NewScanDialog } from "@/components/NewScanDialog";
import {
  Button,
  Card,
  EmptyState,
  ErrorState,
  PageHeader,
  Spinner,
  StatusBadge,
} from "@/components/ui";
import { api } from "@/lib/api";
import { relativeTime, riskBand, riskScore, SEVERITY_ORDER } from "@/lib/format";
import type { Scan, Severity } from "@/lib/types";

// Bound how many completed reports we pull to aggregate portfolio metrics.
const MAX_REPORTS = 20;

export default function OverviewPage() {
  const [dialogOpen, setDialogOpen] = useState(false);

  const scansQuery = useQuery({ queryKey: ["scans"], queryFn: () => api.listScans() });
  const reposQuery = useQuery({ queryKey: ["repos"], queryFn: api.listRepos });

  const scans = scansQuery.data ?? [];
  const repos = reposQuery.data ?? [];
  const repoName = useMemo(
    () => new Map(repos.map((r) => [r.id, r.name])),
    [repos]
  );

  const completedIds = useMemo(
    () => scans.filter((s) => s.status === "completed").slice(0, MAX_REPORTS).map((s) => s.id),
    [scans]
  );

  const reportQueries = useQueries({
    queries: completedIds.map((id) => ({
      queryKey: ["report", id],
      queryFn: () => api.getReport(id),
      staleTime: 60 * 1000,
    })),
  });

  const metrics = useMemo(() => {
    const totals: Record<Severity, number> = { critical: 0, high: 0, medium: 0, low: 0, info: 0 };
    const scores: number[] = [];
    for (const q of reportQueries) {
      if (!q.data) continue;
      for (const sev of SEVERITY_ORDER) totals[sev] += q.data.counts_by_severity[sev] ?? 0;
      scores.push(riskScore(q.data.counts_by_severity));
    }
    const activeVulns = SEVERITY_ORDER.reduce((n, s) => n + totals[s], 0);
    const avgRisk = scores.length
      ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length)
      : 0;
    return { totals, activeVulns, avgRisk };
  }, [reportQueries]);

  if (scansQuery.isLoading) return <Spinner label="Loading your dashboard…" />;
  if (scansQuery.error)
    return <ErrorState message="Could not load your scans. Is the backend reachable?" />;

  const band = riskBand(metrics.avgRisk);
  const running = scans.filter((s) => s.status === "running" || s.status === "pending").length;

  return (
    <>
      <PageHeader
        title="Overview"
        subtitle="Your continuous testing at a glance."
        action={
          repos.length > 0 ? (
            <Button icon={Plus} onClick={() => setDialogOpen(true)}>
              New scan
            </Button>
          ) : null
        }
      />

      {/* Metric cards */}
      <div className="grid grid-cols-2 gap-3.5 lg:grid-cols-4">
        <Stat icon={Radar} label="Total scans" value={scans.length} hint={`${running} in progress`} />
        <Stat
          icon={ShieldAlert}
          label="Active vulnerabilities"
          value={metrics.activeVulns}
          hint={`${metrics.totals.critical} critical · ${metrics.totals.high} high`}
          accent={metrics.totals.critical > 0 ? "#FB5C6B" : undefined}
        />
        <Stat
          icon={Gauge}
          label="Avg risk score"
          value={metrics.avgRisk}
          hint={band.label}
          accent={band.color}
        />
        <Stat icon={GitBranch} label="Repositories" value={repos.length} hint="connected" />
      </div>

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

        {scans.length === 0 ? (
          <EmptyState
            icon={Activity}
            title="No scans yet"
            action={
              repos.length > 0 ? (
                <Button icon={Plus} onClick={() => setDialogOpen(true)}>
                  Launch your first scan
                </Button>
              ) : (
                <Link
                  href="/repos"
                  className="inline-flex items-center justify-center gap-2 rounded-lg bg-cyan px-4 py-2.5 font-display text-[13px] font-semibold text-obsidian transition-all hover:bg-cyan-soft"
                >
                  <GitBranch className="h-4 w-4" strokeWidth={2} />
                  Connect a repository
                </Link>
              )
            }
          >
            {repos.length > 0
              ? "Launch a pentest against one of your connected repositories."
              : "Connect a GitHub repository first, then launch your first pentest."}
          </EmptyState>
        ) : (
          <Card>
            <ul className="divide-y divide-line">
              {scans.slice(0, 6).map((scan) => (
                <RecentScanRow key={scan.id} scan={scan} repoName={repoName.get(scan.repository_id)} />
              ))}
            </ul>
          </Card>
        )}
      </section>

      {dialogOpen ? (
        <NewScanDialog repositories={repos} onClose={() => setDialogOpen(false)} />
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
}: {
  icon: typeof Radar;
  label: string;
  value: number;
  hint?: string;
  accent?: string;
}) {
  return (
    <Card className="p-4">
      <div className="mb-3 flex items-center justify-between">
        <span className="font-mono text-[10px] uppercase tracking-[0.12em] text-faint">{label}</span>
        <Icon className="h-4 w-4 text-faint" strokeWidth={1.75} />
      </div>
      <p className="font-display text-3xl font-bold text-fg" style={accent ? { color: accent } : undefined}>
        {value}
      </p>
      {hint ? <p className="mt-1 text-[11px] text-muted">{hint}</p> : null}
    </Card>
  );
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
        <StatusBadge status={scan.status} />
      </Link>
    </li>
  );
}
