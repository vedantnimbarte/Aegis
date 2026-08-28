"use client";

import { useQuery } from "@tanstack/react-query";
import { Activity, BadgeCheck, Crosshair, Gauge, Radar, ShieldAlert } from "lucide-react";
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
  // target. Summing every scan's report client-side used to count a
  // vulnerability once per re-scan, so a target scanned ten times reported its
  // findings ten times over.
  const summaryQuery = useQuery({
    queryKey: ["dashboard", "summary"],
    queryFn: () => api.dashboardSummary(),
  });
  const scansQuery = useQuery({ queryKey: ["scans"], queryFn: () => api.listScans() });
  const targetsQuery = useQuery({ queryKey: ["targets"], queryFn: () => api.listTargets() });

  const scans = scansQuery.data ?? [];
  const targets = targetsQuery.data ?? [];
  const targetName = useMemo(
    () => new Map(targets.map((t) => [t.id, t.name])),
    [targets]
  );

  return (
    <>
      <PageHeader
        title="Overview"
        subtitle="Your continuous testing at a glance."
        action={<NewScanAction targets={targets} />}
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
            action={<NewScanAction targets={targets} label="Launch your first scan" />}
          >
            {targets.length > 0
              ? "Launch a pentest against one of your targets."
              : "Add a target first — a repository, a live app, an API, or an AI endpoint."}
          </EmptyState>
        ) : (
          <Card>
            <ul className="divide-y divide-line">
              {scans.slice(0, 6).map((scan) => (
                <RecentScanRow
                  key={scan.id}
                  scan={scan}
                  targetName={scan.target_name ?? targetName.get(scan.target_id)}
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
        {/* Not "findings fixed" — findings whose original exploit was re-run
            and no longer works. It is the only number here backed by proof. */}
        <Stat
          icon={BadgeCheck}
          label="Verified fixed"
          value={summary.verified_fixed}
          hint={summary.verified_fixed > 0 ? "exploit re-run and failed" : "none verified yet"}
          accent={summary.verified_fixed > 0 ? "#4ADE80" : undefined}
        />
        <Stat
          icon={Crosshair}
          label="Targets"
          value={summary.connected_targets}
          hint={`${summary.scanned_targets} scanned`}
          href="/targets"
        />
      </div>

      {/* The composition behind "open findings" — and a plain statement of what
          is being counted, since the number is not a sum over scan history. */}
      {summary.scanned_targets > 0 ? (
        <Card className="mt-3.5 space-y-2.5 px-5 py-4">
          <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1.5">
            <SeverityCountList
              counts={summary.counts_by_severity}
              emptyLabel="No open findings"
            />
            <p className="text-[11px] text-faint">
              Latest scan of {summary.scanned_targets}{" "}
              {summary.scanned_targets === 1 ? "target" : "targets"}
              {summary.suppressed_findings > 0
                ? ` · ${summary.suppressed_findings} triaged away`
                : ""}
            </p>
          </div>
          <SeverityBar counts={summary.counts_by_severity} />
        </Card>
      ) : null}

      <div className="mt-3.5 flex justify-end">
        <Link
          href="/costs"
          className="text-[12px] font-medium text-cyan-soft hover:text-cyan"
        >
          What did this cost? →
        </Link>
      </div>
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

function RecentScanRow({ scan, targetName }: { scan: Scan; targetName?: string }) {
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
          <p className="truncate font-mono text-[13px] text-fg">
            {targetName ?? "Unknown target"}
          </p>
          <p className="text-[11px] text-faint">
            {scan.trigger === "retest" ? "retest" : `${scan.scan_mode} scan`} ·{" "}
            {relativeTime(scan.created_at)}
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
