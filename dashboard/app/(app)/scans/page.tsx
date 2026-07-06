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
  Spinner,
  StatusBadge,
} from "@/components/ui";
import { api } from "@/lib/api";
import { formatDuration, relativeTime } from "@/lib/format";

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
  const reposQuery = useQuery({ queryKey: ["repos"], queryFn: api.listRepos });

  const scans = scansQuery.data ?? [];
  const repos = reposQuery.data ?? [];
  const repoName = useMemo(() => new Map(repos.map((r) => [r.id, r.name])), [repos]);

  if (scansQuery.isLoading) return <Spinner label="Loading scans…" />;
  if (scansQuery.error) return <ErrorState message="Could not load scan history." />;

  return (
    <>
      <PageHeader
        title="Scans"
        subtitle="Every pentest run, newest first."
        action={<NewScanAction repositories={repos} />}
      />

      {scans.length === 0 ? (
        <EmptyState
          icon={Radar}
          title="No scans yet"
          action={<NewScanAction repositories={repos} label="Launch a scan" />}
        >
          Once you launch a pentest it will appear here with its live status and results.
        </EmptyState>
      ) : (
        <Card className="overflow-hidden">
          {/* Header row (desktop) */}
          <div className="hidden grid-cols-[1fr_auto_auto_auto_2rem] gap-4 border-b border-line px-4 py-3 font-mono text-[10px] uppercase tracking-wide text-faint sm:grid">
            <span>Repository</span>
            <span className="w-20">Mode</span>
            <span className="w-24">Duration</span>
            <span className="w-28">Status</span>
            <span />
          </div>
          <ul className="divide-y divide-line">
            {scans.map((scan) => (
              <li key={scan.id}>
                <Link
                  href={`/scans/${scan.id}`}
                  className="grid grid-cols-[1fr_auto] items-center gap-4 px-4 py-3.5 transition-colors hover:bg-surface/60 sm:grid-cols-[1fr_auto_auto_auto_2rem]"
                >
                  <div className="min-w-0">
                    <p className="truncate font-mono text-[13px] text-fg">
                      {repoName.get(scan.repository_id) ?? "Unknown repo"}
                    </p>
                    <p className="text-[11px] text-faint">{relativeTime(scan.created_at)}</p>
                  </div>
                  <span className="hidden w-20 font-mono text-[12px] capitalize text-muted sm:block">
                    {scan.scan_mode}
                  </span>
                  <span className="hidden w-24 font-mono text-[12px] text-muted sm:block">
                    {formatDuration(scan.started_at, scan.completed_at)}
                  </span>
                  <span className="justify-self-end sm:w-28 sm:justify-self-start">
                    <StatusBadge status={scan.status} />
                  </span>
                  <ChevronRight className="hidden h-4 w-4 text-faint sm:block" strokeWidth={2} />
                </Link>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </>
  );
}
