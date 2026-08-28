"use client";

import { useQuery } from "@tanstack/react-query";
import { Radar, ChevronRight } from "lucide-react";
import Link from "next/link";
import { useMemo } from "react";

import { NewScanAction } from "@/components/NewScanAction";
import {
  Card,
  EmptyState,
  ErrorState,
  PageHeader,
  SeverityCountList,
  SkeletonList,
  StatusBadge,
} from "@/components/ui";
import { api } from "@/lib/api";
import { formatDuration, relativeTime } from "@/lib/format";
import type { Scan } from "@/lib/types";

/** Target · findings · mode · duration · status · chevron. */
const COLUMNS = "sm:grid-cols-[1fr_8rem_5rem_6rem_7rem_1.5rem]";

export default function ScansPage() {
  const scansQuery = useQuery({
    queryKey: ["scans"],
    queryFn: () => api.listScans(),
    // Poll while anything is still in flight so statuses advance live.
    refetchInterval: (query) => {
      const data = query.state.data ?? [];
      return data.some((s) => s.status === "running" || s.status === "pending") ? 5000 : false;
    },
  });
  const targetsQuery = useQuery({
    queryKey: ["targets"],
    queryFn: () => api.listTargets(),
  });

  const scans = scansQuery.data ?? [];
  const targets = targetsQuery.data ?? [];
  const targetName = useMemo(
    () => new Map(targets.map((t) => [t.id, t.name])),
    [targets]
  );

  return (
    <>
      <PageHeader
        title="Scans"
        subtitle="Every pentest run, newest first."
        action={<NewScanAction targets={targets} />}
      />

      {scansQuery.isLoading ? (
        <SkeletonList rows={6} />
      ) : scansQuery.error ? (
        <ErrorState message="Could not load scan history." />
      ) : scans.length === 0 ? (
        <EmptyState
          icon={Radar}
          title="No scans yet"
          action={<NewScanAction targets={targets} label="Launch a scan" />}
        >
          Once you launch a pentest it will appear here with its live status and results.
        </EmptyState>
      ) : (
        <Card className="overflow-hidden">
          {/* Header row (desktop) */}
          <div
            className={`hidden gap-4 border-b border-line px-4 py-3 font-mono text-[10px] uppercase tracking-wide text-faint sm:grid ${COLUMNS}`}
          >
            <span>Target</span>
            <span>Findings</span>
            <span>Mode</span>
            <span>Duration</span>
            <span>Status</span>
            <span />
          </div>
          <ul className="divide-y divide-line">
            {scans.map((scan) => (
              <li key={scan.id}>
                <ScanRow
                  scan={scan}
                  targetName={scan.target_name ?? targetName.get(scan.target_id)}
                />
              </li>
            ))}
          </ul>
        </Card>
      )}
    </>
  );
}

function ScanRow({ scan, targetName }: { scan: Scan; targetName?: string }) {
  const running = scan.status === "running" || scan.status === "pending";

  return (
    <Link
      href={`/scans/${scan.id}`}
      className={`grid grid-cols-[1fr_auto] items-center gap-4 px-4 py-3.5 transition-colors hover:bg-surface/60 ${COLUMNS}`}
    >
      <div className="min-w-0">
        <p className="truncate font-mono text-[13px] text-fg">{targetName ?? "Unknown repo"}</p>
        <p className="text-[11px] text-faint">
          {scan.trigger === "pull_request" && scan.github_pr_number
            ? `PR #${scan.github_pr_number} · `
            : scan.trigger === "scheduled"
              ? "Scheduled · "
              : ""}
          {relativeTime(scan.created_at)}
        </p>
        {/* Below the name on mobile, where there is no findings column. */}
        {scan.counts_by_severity ? (
          <SeverityCountList
            counts={scan.counts_by_severity}
            emptyLabel="No findings"
            className="mt-1.5 sm:hidden"
          />
        ) : null}
      </div>

      <span className="hidden min-w-0 sm:block">
        {scan.counts_by_severity ? (
          <SeverityCountList counts={scan.counts_by_severity} emptyLabel="No findings" />
        ) : (
          <span className="font-mono text-[11px] text-faint">—</span>
        )}
      </span>

      <span className="hidden font-mono text-[12px] capitalize text-muted sm:block">
        {scan.scan_mode}
      </span>

      <span className="hidden font-mono text-[12px] text-muted sm:block">
        {running ? <InlineProgress scanId={scan.id} /> : formatDuration(scan.started_at, scan.completed_at)}
      </span>

      <span className="justify-self-end sm:justify-self-start">
        <StatusBadge status={scan.status} />
      </span>

      <ChevronRight className="hidden h-4 w-4 text-faint sm:block" strokeWidth={2} />
    </Link>
  );
}

/* -------------------------------------------------------------------------- */
/** Live task counter for an in-flight scan, so the list isn't just "Running".
 *  Renders nothing until Strix's run state exists, which keeps the row quiet
 *  during checkout and sandbox startup. */
function InlineProgress({ scanId }: { scanId: string }) {
  const { data } = useQuery({
    queryKey: ["scan-progress", scanId],
    queryFn: () => api.getScanProgress(scanId),
    refetchInterval: 5000,
    retry: false,
  });

  if (!data || data.steps.length === 0) return <span className="text-faint">—</span>;
  const done = data.steps.filter((s) => s.status === "done").length;
  return (
    <span className="text-cyan-soft">
      {done}/{data.steps.length} tasks
    </span>
  );
}
