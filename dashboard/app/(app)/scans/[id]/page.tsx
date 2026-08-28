"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Check,
  ChevronDown,
  ChevronsDownUp,
  ChevronsUpDown,
  Circle,
  Download,
  ExternalLink,
  Github,
  GitPullRequest,
  Link2,
  Radar,
  ShieldCheck,
  XCircle,
  FileWarning,
  FileCheck,
  FileJson,
  Loader2,
  AlertTriangle,
  BadgeCheck,
  Link as LinkIcon,
  Network,
  RefreshCw,
  Share2,
  Trash2,
  Wrench,
} from "lucide-react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useEffect, useMemo, useState } from "react";

import { CodeBlock, Markdown } from "@/components/Markdown";
import { useToast } from "@/components/Toast";
import {
  Button,
  Card,
  cn,
  ErrorState,
  Pill,
  SeverityBar,
  SeverityBadge,
  Skeleton,
  Spinner,
  StatusBadge,
} from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import {
  formatDate,
  formatDuration,
  riskBand,
  riskScore,
  SEVERITY_ORDER,
} from "@/lib/format";
import type {
  AttackChain,
  Evidence,
  ProgressStep,
  TriageStatus,
  Scan,
  ScanReport,
  Severity,
  Vulnerability,
} from "@/lib/types";

/** Hands a fetched blob to the browser as a download. */
function saveBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export default function ScanDetailPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [sharing, setSharing] = useState(false);

  const scanQuery = useQuery({
    queryKey: ["scan", id],
    queryFn: () => api.getScan(id),
    refetchInterval: (query) => {
      const s = query.state.data;
      return s && (s.status === "running" || s.status === "pending") ? 4000 : false;
    },
  });

  const scan = scanQuery.data;
  const isComplete = scan?.status === "completed";

  const reportQuery = useQuery({
    queryKey: ["report", id],
    queryFn: () => api.getReport(id),
    enabled: isComplete,
  });

  const targetsQuery = useQuery({
    queryKey: ["targets"],
    queryFn: () => api.listTargets(),
  });
  const target = useMemo(
    () => (targetsQuery.data ?? []).find((t) => t.id === scan?.target_id),
    [targetsQuery.data, scan?.target_id]
  );
  const targetName = scan?.target_name ?? target?.name;

  const cancel = useMutation({
    mutationFn: () => api.cancelScan(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["scan", id] });
      toast.success("Scan canceled.");
    },
    onError: (err) =>
      toast.fromError(err, "Could not cancel this scan. It may have just finished."),
  });

  const download = useMutation({
    mutationFn: (variant: "plain" | "compliance" | "sarif") =>
      variant === "sarif"
        ? api.getReportSarif(id)
        : api.getReportPdf(id, variant === "compliance"),
    onSuccess: (blob, variant) => {
      const extension = variant === "sarif" ? "sarif" : "pdf";
      const prefix = variant === "compliance" ? "aegis-compliance-report" : "aegis-report";
      saveBlob(blob, `${prefix}-${id}.${extension}`);
      toast.success("Report exported.");
    },
    onError: (err) => toast.fromError(err, "Could not export the report. Please try again."),
  });

  if (scanQuery.isLoading) return <ScanDetailSkeleton />;
  if (scanQuery.error || !scan) return <ErrorState message="Scan not found." />;

  return (
    <>
      <Link
        href="/scans"
        className="mb-6 inline-flex items-center gap-1.5 text-[12px] font-medium text-muted hover:text-fg"
      >
        <ArrowLeft className="h-3.5 w-3.5" strokeWidth={2} />
        All scans
      </Link>

      {/* Header */}
      <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-3">
          <span className="grid h-11 w-11 shrink-0 place-items-center rounded-xl border border-line bg-ink text-cyan-soft">
            <Radar className="h-5 w-5" strokeWidth={1.75} />
          </span>
          <div>
            <h1 className="font-mono text-lg font-semibold text-fg">
              {targetName ?? "Target"}
            </h1>
            <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[11px] text-faint">
              <span className="capitalize">
                {scan.trigger === "retest" ? "verification retest" : `${scan.scan_mode} scan`}
              </span>
              <span>·</span>
              <span>Started {formatDate(scan.started_at ?? scan.created_at)}</span>
              <span>·</span>
              <span>{formatDuration(scan.started_at, scan.completed_at)}</span>
              {scan.engine_model ? (
                <>
                  <span>·</span>
                  <span>{scan.engine_model}</span>
                </>
              ) : null}
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {scan.status === "pending" || scan.status === "running" ? (
            <Button
              variant="secondary"
              icon={XCircle}
              loading={cancel.isPending}
              onClick={() => cancel.mutate()}
            >
              Cancel scan
            </Button>
          ) : null}
          {scan.status === "completed" ? (
            <>
              <Button
                variant="secondary"
                icon={Download}
                loading={download.isPending && download.variables === "plain"}
                onClick={() => download.mutate("plain")}
              >
                PDF
              </Button>
              {/* The document an auditor accepts: scope, methodology, control
                  mappings, limitations, and a signed attestation letter. */}
              <Button
                variant="secondary"
                icon={FileCheck}
                loading={download.isPending && download.variables === "compliance"}
                onClick={() => download.mutate("compliance")}
              >
                Compliance pack
              </Button>
              <Button
                variant="secondary"
                icon={FileJson}
                loading={download.isPending && download.variables === "sarif"}
                onClick={() => download.mutate("sarif")}
              >
                SARIF
              </Button>
              <Button variant="secondary" icon={Share2} onClick={() => setSharing(true)}>
                Share
              </Button>
            </>
          ) : null}
          <StatusBadge status={scan.status} />
        </div>
      </div>

      {sharing ? <ShareDialog scanId={id} onClose={() => setSharing(false)} /> : null}

      {/* A retest answers one question, so it says so plainly rather than
          rendering as a scan that mysteriously found one thing or nothing. */}
      {scan.trigger === "retest" ? <RetestVerdict scan={scan} /> : null}

      {scan.custom_instructions ? (
        <Card className="mb-6 px-4 py-3">
          <p className="font-mono text-[10px] uppercase tracking-wide text-faint">Instructions</p>
          <p className="mt-1 text-[13px] leading-relaxed text-muted">{scan.custom_instructions}</p>
        </Card>
      ) : null}

      {/* Run cost — only known once the worker has ingested the run. */}
      {scan.cost_usd != null || scan.llm_requests != null ? (
        <Card className="mb-6 flex flex-wrap items-center gap-x-8 gap-y-2 px-5 py-3.5">
          <span className="font-mono text-[10px] uppercase tracking-wide text-faint">
            Run cost
          </span>
          {scan.cost_usd != null ? (
            <span className="text-[13px] text-muted">
              Spend <span className="font-mono text-fg">${scan.cost_usd.toFixed(2)}</span>
            </span>
          ) : null}
          {scan.llm_requests != null ? (
            <span className="text-[13px] text-muted">
              Model calls{" "}
              <span className="font-mono text-fg">{scan.llm_requests.toLocaleString()}</span>
            </span>
          ) : null}
          {scan.input_tokens != null ? (
            <span className="text-[13px] text-muted">
              Tokens{" "}
              <span className="font-mono text-fg">
                {(scan.input_tokens / 1_000_000).toFixed(2)}M in
                {scan.output_tokens != null
                  ? ` · ${(scan.output_tokens / 1000).toFixed(0)}k out`
                  : ""}
              </span>
            </span>
          ) : null}
        </Card>
      ) : null}

      {/* Body by status */}
      {scan.status === "pending" || scan.status === "running" ? (
        <InProgress scan={scan} />
      ) : scan.status === "failed" || scan.status === "canceled" ? (
        <FailedState scan={scan} />
      ) : reportQuery.isLoading ? (
        <Spinner label="Loading report…" />
      ) : reportQuery.error || !reportQuery.data ? (
        <ErrorState message="Could not load the report for this scan." />
      ) : (
        <Report report={reportQuery.data} />
      )}
    </>
  );
}

/* -------------------------------------------------------------------------- */
function ScanDetailSkeleton() {
  return (
    <>
      <Skeleton className="mb-6 h-3 w-24" />
      <div className="mb-8 flex items-start gap-3">
        <Skeleton className="h-11 w-11 shrink-0 rounded-xl" />
        <div className="flex-1 space-y-2.5">
          <Skeleton className="h-5 w-56" />
          <Skeleton className="h-3 w-72" />
        </div>
      </div>
      <Card className="mb-6 space-y-3 p-5">
        <Skeleton className="h-3 w-32" />
        <Skeleton className="h-8 w-48" />
      </Card>
      <div className="space-y-3">
        {Array.from({ length: 4 }, (_, i) => (
          <Card key={i} className="flex items-center gap-3 px-4 py-4">
            <Skeleton className="h-5 w-20 shrink-0 rounded-md" />
            <Skeleton className="h-3.5 flex-1" />
          </Card>
        ))}
      </div>
    </>
  );
}

/* -------------------------------------------------------------------------- */
const PHASE_LABEL: Record<string, string> = {
  preparing: "Cloning the repository and starting the sandbox",
  starting: "Starting the agent run",
  running: "Agents are probing the codebase",
};

function StepIcon({ status }: { status: ProgressStep["status"] }) {
  if (status === "done")
    return <Check className="h-3.5 w-3.5 text-signal" strokeWidth={2.5} />;
  if (status === "active")
    return <Loader2 className="h-3.5 w-3.5 animate-spin text-cyan-soft" strokeWidth={2.5} />;
  return <Circle className="h-3.5 w-3.5 text-faint" strokeWidth={2} />;
}

function InProgress({ scan }: { scan: Scan }) {
  // Strix's run state only appears once the sandbox is up, so this polls
  // independently of the scan record and simply renders less when empty.
  const progressQuery = useQuery({
    queryKey: ["scan-progress", scan.id],
    queryFn: () => api.getScanProgress(scan.id),
    refetchInterval: 4000,
    retry: false,
  });

  const progress = progressQuery.data;
  const steps = progress?.steps ?? [];
  const agents = (progress?.agents ?? []).filter((a) => a.name !== "Root Agent");
  const done = steps.filter((s) => s.status === "done").length;

  const headline =
    scan.status === "pending"
      ? "Queued for scanning"
      : PHASE_LABEL[progress?.phase ?? ""] ?? "Pentest in progress";

  return (
    <div className="space-y-4">
      <Card className="px-5 py-4">
        <div className="flex items-center gap-3">
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-cyan/30 bg-cyan/10 text-cyan-soft">
            <Loader2 className="h-4 w-4 animate-spin" strokeWidth={2} />
          </span>
          <div className="min-w-0 flex-1">
            <h3 className="font-display text-[15px] font-semibold text-fg">{headline}</h3>
            <p className="mt-0.5 text-[12px] text-muted">
              {steps.length > 0
                ? `${done} of ${steps.length} tasks complete`
                : "This page updates automatically."}
            </p>
          </div>
          {progress && progress.llm_requests > 0 ? (
            <div className="hidden shrink-0 gap-5 sm:flex">
              <div className="text-right">
                <p className="font-mono text-[10px] uppercase tracking-wide text-faint">
                  Model calls
                </p>
                <p className="font-mono text-[13px] text-fg">
                  {progress.llm_requests.toLocaleString()}
                </p>
              </div>
              {progress.cost_usd !== null ? (
                <div className="text-right">
                  <p className="font-mono text-[10px] uppercase tracking-wide text-faint">
                    Spend
                  </p>
                  <p className="font-mono text-[13px] text-fg">
                    ${progress.cost_usd.toFixed(2)}
                  </p>
                </div>
              ) : null}
            </div>
          ) : null}
        </div>
      </Card>

      {agents.length > 0 ? (
        <Card className="px-5 py-4">
          <p className="mb-3 font-mono text-[10px] uppercase tracking-wide text-faint">
            Active agents
          </p>
          <div className="flex flex-wrap gap-2">
            {agents.map((agent) => (
              <Pill
                key={agent.name}
                tone={
                  agent.status === "running"
                    ? "border-cyan/30 bg-cyan/10 text-cyan-soft"
                    : "border-line bg-ink text-muted"
                }
              >
                <span
                  className={
                    agent.status === "running"
                      ? "mr-1.5 inline-block h-1.5 w-1.5 rounded-full bg-cyan"
                      : "mr-1.5 inline-block h-1.5 w-1.5 rounded-full bg-faint"
                  }
                />
                {agent.name}
              </Pill>
            ))}
          </div>
        </Card>
      ) : null}

      {steps.length > 0 ? (
        <Card className="px-5 py-4">
          <p className="mb-3 font-mono text-[10px] uppercase tracking-wide text-faint">
            Steps
          </p>
          <ol className="space-y-2.5">
            {steps.map((step, i) => (
              <li key={`${step.title}-${i}`} className="flex gap-2.5">
                <span className="mt-0.5 shrink-0">
                  <StepIcon status={step.status} />
                </span>
                <div className="min-w-0">
                  <p
                    className={
                      step.status === "done"
                        ? "text-[13px] text-muted"
                        : "text-[13px] text-fg"
                    }
                  >
                    {step.title}
                  </p>
                  {step.detail ? (
                    <p className="mt-0.5 text-[12px] leading-relaxed text-faint">
                      {step.detail}
                    </p>
                  ) : null}
                </div>
              </li>
            ))}
          </ol>
        </Card>
      ) : null}
    </div>
  );
}

function FailedState({ scan }: { scan: Scan }) {
  // A canceled scan is a deliberate stop, not a fault — don't dress it in red.
  const canceled = scan.status === "canceled";
  return (
    <Card className="px-5 py-6">
      <div className="flex items-start gap-3">
        <span
          className={cn(
            "grid h-9 w-9 shrink-0 place-items-center rounded-lg border",
            canceled
              ? "border-line bg-ink text-muted"
              : "border-danger/30 bg-danger/10 text-danger"
          )}
        >
          {canceled ? (
            <XCircle className="h-4 w-4" strokeWidth={2} />
          ) : (
            <AlertTriangle className="h-4 w-4" strokeWidth={2} />
          )}
        </span>
        <div>
          <h3 className="font-display text-[15px] font-semibold text-fg">
            {canceled ? "Scan canceled" : "Scan failed"}
          </h3>
          <p className="mt-1.5 text-[13px] leading-relaxed text-muted">
            {canceled
              ? "You stopped this scan before it finished, so there are no results."
              : scan.error_message ||
                "The scan did not complete. Please try launching it again."}
          </p>
        </div>
      </div>
    </Card>
  );
}

/* -------------------------------------------------------------------------- */
function Report({ report }: { report: ScanReport }) {
  const score = riskScore(report.counts_by_severity);
  const band = riskBand(score);

  // Filter state. An empty severity set means "no severity filter" rather than
  // "hide everything" — a filter nobody has touched shouldn't blank the page.
  const [severities, setSeverities] = useState<Set<Severity>>(new Set());
  const [showTriaged, setShowTriaged] = useState(false);
  // Bumping the nonce remounts the cards, which is how expand/collapse-all
  // resets every <details> without making each one a controlled component.
  const [expand, setExpand] = useState<{ open: boolean; nonce: number }>({
    open: false,
    nonce: 0,
  });

  // A shared #finding-<id> link should land on that finding, open.
  const [linkedId, setLinkedId] = useState<string | null>(null);
  useEffect(() => {
    const hash = window.location.hash.replace(/^#finding-/, "");
    if (!hash || hash === window.location.hash) return;
    setLinkedId(hash);
    document.getElementById(`finding-${hash}`)?.scrollIntoView({ block: "center" });
  }, []);

  const sorted = useMemo(
    () =>
      SEVERITY_ORDER.flatMap((sev) =>
        report.vulnerabilities.filter((v) => v.severity === sev)
      ),
    [report.vulnerabilities]
  );

  const visible = sorted.filter((v) => {
    if (severities.size > 0 && !severities.has(v.severity)) return false;
    // The linked finding always shows, so a shared link can't land on a
    // finding the default filter has hidden.
    if (v.id === linkedId) return true;
    if (!showTriaged && v.triage_status !== "open") return false;
    return true;
  });

  const toggleSeverity = (sev: Severity) =>
    setSeverities((current) => {
      const next = new Set(current);
      if (!next.delete(sev)) next.add(sev);
      return next;
    });

  if (report.total === 0) {
    return (
      <Card className="flex flex-col items-center justify-center px-6 py-16 text-center">
        <span className="mb-4 grid h-12 w-12 place-items-center rounded-xl border border-signal/30 bg-signal/10 text-signal">
          <ShieldCheck className="h-6 w-6" strokeWidth={2} />
        </span>
        <h3 className="font-display text-[15px] font-semibold text-fg">No vulnerabilities found</h3>
        <p className="mt-1.5 max-w-sm text-[13px] leading-relaxed text-muted">
          Aegis completed the pentest and could not exploit any vulnerabilities in this run.
        </p>
      </Card>
    );
  }

  return (
    <>
      {/* Summary */}
      <Card className="mb-6 p-5">
        <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex flex-wrap gap-2">
            {SEVERITY_ORDER.map((sev) => {
              const count = report.counts_by_severity[sev] ?? 0;
              if (count === 0) return null;
              const on = severities.has(sev);
              return (
                <button
                  key={sev}
                  type="button"
                  aria-pressed={on}
                  onClick={() => toggleSeverity(sev)}
                  className={cn(
                    "flex items-center gap-2 rounded-lg border px-3 py-2 transition-colors",
                    on ? "border-cyan/50 bg-cyan/[0.07]" : "border-line bg-ink hover:border-line"
                  )}
                >
                  <SeverityBadge severity={sev} />
                  <span className="font-display text-sm font-bold text-fg">{count}</span>
                </button>
              );
            })}
          </div>
          <div className="flex items-center gap-3 sm:flex-col sm:items-end">
            <span className="font-mono text-[10px] uppercase tracking-wide text-faint">
              Risk score
            </span>
            <span className="font-display text-3xl font-bold" style={{ color: band.color }}>
              {score}
              <span className="ml-1 text-sm font-medium text-muted">/ 100</span>
            </span>
          </div>
        </div>
        <SeverityBar counts={report.counts_by_severity} className="mt-5" />
      </Card>

      {report.diff.has_baseline ? (
        <Card className="mb-6 flex flex-wrap items-center gap-x-6 gap-y-2 px-5 py-3.5">
          <span className="font-mono text-[10px] uppercase tracking-wide text-faint">
            Since last scan
          </span>
          <span className="text-[13px] text-fg">
            <span className="font-display font-bold text-danger">{report.diff.new_count}</span>{" "}
            <span className="text-muted">new</span>
          </span>
          <span className="text-[13px] text-fg">
            <span className="font-display font-bold text-signal">{report.diff.fixed_count}</span>{" "}
            <span className="text-muted">fixed</span>
          </span>
          <span className="text-[13px] text-fg">
            <span className="font-display font-bold text-fg">
              {report.diff.persisting_count}
            </span>{" "}
            <span className="text-muted">still open</span>
          </span>
          {report.verified_fixed_count > 0 ? (
            <span className="text-[13px] text-fg">
              <span className="font-display font-bold text-signal">
                {report.verified_fixed_count}
              </span>{" "}
              <span className="text-muted">verified fixed</span>
            </span>
          ) : null}
        </Card>
      ) : null}

      <AttackChains chains={report.attack_chains} />
      <AutofixCard report={report} />

      {/* Findings toolbar — sticks below the mobile top bar while scrolling a
          long report, so the filters stay reachable. */}
      <div className="sticky top-14 z-10 -mx-1 mb-3 flex flex-wrap items-center gap-x-3 gap-y-2 rounded-lg border border-line bg-ink/95 px-4 py-2.5 backdrop-blur lg:top-0">
        <span className="font-mono text-[11px] text-muted">
          {visible.length === sorted.length
            ? `${sorted.length} findings`
            : `${visible.length} of ${sorted.length} findings`}
        </span>

        {severities.size > 0 ? (
          <button
            type="button"
            onClick={() => setSeverities(new Set())}
            className="font-mono text-[11px] text-cyan-soft hover:text-cyan"
          >
            Clear severity filter
          </button>
        ) : null}

        <div className="ml-auto flex items-center gap-2">
          {report.suppressed_count > 0 ? (
            <button
              type="button"
              aria-pressed={showTriaged}
              onClick={() => setShowTriaged((v) => !v)}
              className={cn(
                "rounded-md border px-2.5 py-1 font-mono text-[11px] transition-colors",
                showTriaged
                  ? "border-cyan/40 bg-cyan/10 text-cyan-soft"
                  : "border-line bg-ink text-faint hover:text-muted"
              )}
            >
              {showTriaged ? "Hide" : "Show"} {report.suppressed_count} triaged
            </button>
          ) : null}
          <button
            type="button"
            onClick={() => setExpand((e) => ({ open: !e.open, nonce: e.nonce + 1 }))}
            className="inline-flex items-center gap-1.5 rounded-md border border-line bg-ink px-2.5 py-1 font-mono text-[11px] text-faint transition-colors hover:text-muted"
          >
            {expand.open ? (
              <ChevronsDownUp className="h-3 w-3" strokeWidth={2} />
            ) : (
              <ChevronsUpDown className="h-3 w-3" strokeWidth={2} />
            )}
            {expand.open ? "Collapse all" : "Expand all"}
          </button>
        </div>
      </div>

      {/* Findings */}
      {visible.length === 0 ? (
        <Card className="px-5 py-10 text-center">
          <p className="text-[13px] text-muted">No findings match the current filters.</p>
          <button
            type="button"
            onClick={() => {
              setSeverities(new Set());
              setShowTriaged(true);
            }}
            className="mt-2 font-mono text-[12px] text-cyan-soft hover:text-cyan"
          >
            Show everything
          </button>
        </Card>
      ) : (
        <div className="space-y-3">
          {visible.map((vuln) => (
            <VulnerabilityCard
              key={`${vuln.id}-${expand.nonce}`}
              vuln={vuln}
              scanId={report.scan.id}
              defaultOpen={expand.open || vuln.id === linkedId}
            />
          ))}
        </div>
      )}
    </>
  );
}

/* -------------------------------------------------------------------------- */
function AutofixCard({ report }: { report: ScanReport }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const scan = report.scan;

  const autofix = useMutation({
    mutationFn: () => api.generateFixPr(scan.id),
    onSuccess: ({ pull_request_url }) => {
      queryClient.invalidateQueries({ queryKey: ["scan", scan.id] });
      queryClient.invalidateQueries({ queryKey: ["report", scan.id] });
      toast.success("Fix pull request opened.");
      window.open(pull_request_url, "_blank", "noopener");
    },
  });

  // Already opened a PR.
  if (scan.autofix_pr_url) {
    return (
      <Card className="mb-6 flex flex-col gap-2 p-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2.5 text-[13px] text-fg">
          <GitPullRequest className="h-4 w-4 shrink-0 text-signal" strokeWidth={2} />
          Auto-fix pull request opened.
        </div>
        <a
          href={scan.autofix_pr_url}
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 text-[12px] font-semibold text-cyan-soft hover:text-cyan"
        >
          View pull request →
        </a>
      </Card>
    );
  }

  if (report.fixable_count === 0) return null;

  const err = autofix.error instanceof ApiError ? autofix.error : null;
  const needsInstall = err?.reason === "no_installation";
  const needsUpgrade = err?.status === 402;

  return (
    <Card className="mb-6 p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex items-center gap-2.5">
          <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-cyan/40 bg-cyan/10 text-cyan-soft">
            <Wrench className="h-4 w-4" strokeWidth={2} />
          </span>
          <p className="text-[13px] leading-relaxed text-fg">
            {report.fixable_count} finding{report.fixable_count !== 1 ? "s have" : " has"}{" "}
            a suggested fix. Open a pull request applying{" "}
            {report.fixable_count !== 1 ? "them" : "it"}.
          </p>
        </div>
        <Button
          icon={GitPullRequest}
          loading={autofix.isPending}
          onClick={() => autofix.mutate()}
          className="shrink-0"
        >
          Generate fix PR
        </Button>
      </div>

      {/* Kept inline rather than as a toast: both branches need a follow-up
          link, and the error explains the disabled action sitting next to it. */}
      {err ? (
        <div className="mt-3 space-y-2">
          <ErrorState message={err.message} />
          {needsInstall ? (
            <Link href="/settings" className="text-[12px] font-medium text-cyan-soft hover:text-cyan">
              Install the GitHub App →
            </Link>
          ) : needsUpgrade ? (
            <Link href="/billing" className="text-[12px] font-medium text-cyan-soft hover:text-cyan">
              View plans & upgrade →
            </Link>
          ) : null}
        </div>
      ) : null}
    </Card>
  );
}

/* -------------------------------------------------------------------------- */
/** Findings that compose into an outcome none of them reaches alone.
 *
 *  This is the part of a manual engagement that scanners drop: two mediums
 *  that chain into account takeover are one critical, and reading them as
 *  separate rows is how a real risk gets deprioritized. */
function AttackChains({ chains }: { chains: AttackChain[] }) {
  if (!chains || chains.length === 0) return null;

  return (
    <Card className="mb-6 p-5">
      <div className="mb-3 flex items-center gap-2">
        <Network className="h-4 w-4 text-cyan-soft" strokeWidth={2} />
        <h3 className="font-display text-[15px] font-semibold text-fg">Attack chains</h3>
      </div>
      <p className="mb-4 text-[13px] leading-relaxed text-muted">
        Individually these findings are limited. Combined, each group below
        reaches an outcome none of its parts reaches alone.
      </p>
      <ul className="space-y-3">
        {chains.map((chain, i) => (
          <li key={i} className="rounded-lg border border-line bg-ink px-4 py-3">
            <div className="flex flex-wrap items-center gap-2">
              <SeverityBadge severity={chain.severity} />
              <span className="font-display text-[14px] font-semibold text-fg">
                {chain.title}
              </span>
            </div>
            <p className="mt-2 text-[13px] leading-relaxed text-muted">{chain.narrative}</p>
            {chain.steps.length > 0 ? (
              <ol className="mt-2.5 space-y-1">
                {chain.steps.map((step, j) => (
                  <li key={j} className="flex gap-2 text-[12px] text-muted">
                    <span className="font-mono text-faint">{j + 1}.</span>
                    <span>{step}</span>
                  </li>
                ))}
              </ol>
            ) : null}
          </li>
        ))}
      </ul>
    </Card>
  );
}

/* -------------------------------------------------------------------------- */
const RETEST_COPY: Record<
  string,
  { title: string; body: string; tone: string; icon: typeof BadgeCheck }
> = {
  fixed: {
    title: "Verified fixed",
    body: "The original proof of concept was re-run against the target and no longer succeeds.",
    tone: "border-signal/30 bg-signal/10 text-signal",
    icon: BadgeCheck,
  },
  still_vulnerable: {
    title: "Still vulnerable",
    body: "The original proof of concept was re-run and still succeeds. The finding remains open.",
    tone: "border-danger/30 bg-danger/10 text-danger",
    icon: AlertTriangle,
  },
  inconclusive: {
    title: "Retest inconclusive",
    body: "The retest could not complete, so nothing was proven either way. The finding is unchanged.",
    tone: "border-amber/30 bg-amber/10 text-amber",
    icon: AlertTriangle,
  },
};

/** The verdict banner on a retest scan.
 *
 *  "Inconclusive" is deliberately not folded into "fixed": a tool that reports
 *  a vulnerability as remediated because it crashed before checking is worse
 *  than one that reports nothing. */
function RetestVerdict({ scan }: { scan: Scan }) {
  const copy = scan.retest_outcome ? RETEST_COPY[scan.retest_outcome] : null;
  if (!copy) {
    return (
      <Card className="mb-6 flex items-center gap-3 px-5 py-4">
        <Loader2 className="h-4 w-4 animate-spin text-cyan-soft" strokeWidth={2} />
        <p className="text-[13px] text-muted">
          Re-running this finding&apos;s proof of concept…
        </p>
      </Card>
    );
  }
  const Icon = copy.icon;
  return (
    <Card className={cn("mb-6 flex items-start gap-3 px-5 py-4", copy.tone)}>
      <Icon className="mt-0.5 h-4 w-4 shrink-0" strokeWidth={2} />
      <div>
        <h3 className="font-display text-[14px] font-semibold">{copy.title}</h3>
        <p className="mt-1 text-[13px] leading-relaxed opacity-90">{copy.body}</p>
      </div>
    </Card>
  );
}

/* -------------------------------------------------------------------------- */
/** Expiring public links to this report.
 *
 *  For handing a report to a prospect's security reviewer or an auditor
 *  without creating them an account. Proof-of-concept code is withheld by
 *  default — a working exploit against production is not what they asked for. */
function ShareDialog({ scanId, onClose }: { scanId: string; onClose: () => void }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [label, setLabel] = useState("");
  const [days, setDays] = useState("14");
  const [includePoc, setIncludePoc] = useState(false);
  const [minted, setMinted] = useState<string | null>(null);

  const sharesQuery = useQuery({
    queryKey: ["shares", scanId],
    queryFn: () => api.listShares(scanId),
  });

  const create = useMutation({
    mutationFn: () =>
      api.createShare(scanId, {
        label: label.trim() || null,
        expires_in_days: Number(days) || null,
        include_poc: includePoc,
      }),
    onSuccess: (share) => {
      setMinted(share.url);
      setLabel("");
      queryClient.invalidateQueries({ queryKey: ["shares", scanId] });
      navigator.clipboard.writeText(share.url).catch(() => undefined);
      toast.success("Share link created and copied.");
    },
    onError: (err) => toast.fromError(err, "Could not create the share link."),
  });

  const revoke = useMutation({
    mutationFn: (shareId: string) => api.revokeShare(scanId, shareId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["shares", scanId] });
      toast.success("Link revoked.");
    },
    onError: (err) => toast.fromError(err, "Could not revoke that link."),
  });

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const shares = sharesQuery.data ?? [];

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-obsidian/70 p-4 backdrop-blur-sm sm:items-center"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div
        className="w-full max-w-lg overflow-hidden rounded-2xl border border-line bg-surface shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-line px-5 py-4">
          <div className="flex items-center gap-2.5">
            <span className="grid h-8 w-8 place-items-center rounded-lg border border-cyan/40 bg-cyan/10 text-cyan-soft">
              <Share2 className="h-4 w-4" strokeWidth={2} />
            </span>
            <h2 className="font-display text-[15px] font-semibold text-fg">Share this report</h2>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="grid h-8 w-8 place-items-center rounded-lg text-faint hover:bg-ink hover:text-fg"
          >
            <XCircle className="h-4 w-4" strokeWidth={2} />
          </button>
        </div>

        <div className="space-y-4 px-5 py-5">
          <div className="grid gap-3 sm:grid-cols-2">
            <div>
              <label className="mb-1.5 block font-mono text-[11px] uppercase tracking-wide text-faint">
                Who is it for
              </label>
              <input
                value={label}
                onChange={(e) => setLabel(e.target.value)}
                placeholder="Acme security review"
                className="w-full rounded-lg border border-line bg-ink px-3 py-2.5 text-[13px] text-fg placeholder:text-faint focus:border-cyan/60"
              />
            </div>
            <div>
              <label className="mb-1.5 block font-mono text-[11px] uppercase tracking-wide text-faint">
                Expires in (days)
              </label>
              <input
                value={days}
                onChange={(e) => setDays(e.target.value)}
                inputMode="numeric"
                className="w-full rounded-lg border border-line bg-ink px-3 py-2.5 font-mono text-[13px] text-fg focus:border-cyan/60"
              />
            </div>
          </div>

          <label className="flex items-start gap-2.5 rounded-lg border border-line bg-ink px-3 py-2.5">
            <input
              type="checkbox"
              checked={includePoc}
              onChange={(e) => setIncludePoc(e.target.checked)}
              className="mt-0.5 h-4 w-4 shrink-0 accent-cyan"
            />
            <span className="text-[12px] leading-relaxed text-muted">
              Include proof-of-concept exploits and request transcripts. Off by
              default — a reviewer needs to see that you tested and fixed, not a
              working exploit against your production system.
            </span>
          </label>

          {minted ? (
            <div className="rounded-lg border border-signal/30 bg-signal/[0.07] px-3 py-2.5">
              <p className="mb-1.5 font-mono text-[10px] uppercase tracking-wide text-signal">
                Link created — copy it now
              </p>
              <p className="break-all font-mono text-[11px] text-fg">{minted}</p>
            </div>
          ) : null}

          {shares.length > 0 ? (
            <div>
              <p className="mb-2 font-mono text-[10px] uppercase tracking-wide text-faint">
                Active links
              </p>
              <ul className="space-y-1.5">
                {shares.map((share) => (
                  <li
                    key={share.id}
                    className="flex items-center gap-2 rounded-lg border border-line bg-ink px-3 py-2"
                  >
                    <LinkIcon className="h-3.5 w-3.5 shrink-0 text-faint" strokeWidth={2} />
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-[12px] text-fg">
                        {share.label ?? "Untitled link"}
                      </p>
                      <p className="text-[11px] text-faint">
                        Expires {formatDate(share.expires_at)} · {share.view_count}{" "}
                        {share.view_count === 1 ? "view" : "views"}
                        {share.include_poc ? " · includes PoC" : ""}
                      </p>
                    </div>
                    <button
                      type="button"
                      aria-label="Revoke this link"
                      onClick={() => revoke.mutate(share.id)}
                      className="grid h-7 w-7 shrink-0 place-items-center rounded-md text-faint hover:bg-surface hover:text-danger"
                    >
                      <Trash2 className="h-3.5 w-3.5" strokeWidth={2} />
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>

        <div className="flex items-center justify-end gap-2.5 border-t border-line px-5 py-4">
          <Button variant="ghost" onClick={onClose}>
            Done
          </Button>
          <Button icon={Share2} loading={create.isPending} onClick={() => create.mutate()}>
            Create link
          </Button>
        </div>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
const TRIAGE_CHOICES: { value: TriageStatus; label: string }[] = [
  { value: "open", label: "Open" },
  { value: "false_positive", label: "False positive" },
  { value: "accepted_risk", label: "Accepted risk" },
  { value: "fixed", label: "Fixed" },
];

const TRIAGE_TONE: Record<TriageStatus, string> = {
  open: "border-line bg-ink text-muted",
  false_positive: "border-line bg-ink text-faint",
  accepted_risk: "border-amber/30 bg-amber/10 text-amber",
  fixed: "border-signal/30 bg-signal/10 text-signal",
};

function VulnerabilityCard({
  vuln,
  scanId,
  defaultOpen,
}: {
  vuln: Vulnerability;
  scanId: string;
  defaultOpen?: boolean;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  // Controlled rather than leaning on React's diffing of the `open` attribute,
  // so a re-render (a triage save, a refetch) can never snap the card shut
  // under the reader. Expand/collapse-all remounts via `key`, re-seeding this.
  const [open, setOpen] = useState(defaultOpen ?? false);
  const triage = useMutation({
    mutationFn: (status: TriageStatus) => api.triageFinding(scanId, vuln.id, { status }),
    onSuccess: (_data, status) => {
      // Refetch the report so the diff/suppressed counts stay in step.
      queryClient.invalidateQueries({ queryKey: ["report", scanId] });
      queryClient.invalidateQueries({ queryKey: ["scans"] });
      queryClient.invalidateQueries({ queryKey: ["dashboard", "summary"] });
      const label = TRIAGE_CHOICES.find((c) => c.value === status)?.label ?? status;
      toast.success(`Marked as ${label.toLowerCase()}.`);
    },
    onError: (err) => toast.fromError(err, "Could not save that verdict."),
  });

  const status = vuln.triage_status;
  const suppressed = status !== "open";
  const meta: { k: string; v: string }[] = [];
  if (vuln.cvss_score != null) meta.push({ k: "CVSS", v: vuln.cvss_score.toFixed(1) });
  if (vuln.owasp_category) meta.push({ k: "Class", v: vuln.owasp_category });
  if (vuln.file_path) meta.push({ k: "Location", v: vuln.file_path });

  return (
    <Card id={`finding-${vuln.id}`} className="overflow-hidden scroll-mt-24">
      <details
        className="group"
        open={open}
        onToggle={(e) => setOpen(e.currentTarget.open)}
      >
        <summary className="flex cursor-pointer list-none items-center gap-3 px-4 py-3.5 transition-colors hover:bg-surface/60 [&::-webkit-details-marker]:hidden">
          <SeverityBadge severity={vuln.severity} />
          <span
            className={
              suppressed
                ? "min-w-0 flex-1 truncate font-display text-[14px] font-semibold text-muted line-through decoration-faint"
                : "min-w-0 flex-1 truncate font-display text-[14px] font-semibold text-fg"
            }
          >
            {vuln.title}
          </span>
          {vuln.is_new ? (
            <span className="hidden shrink-0 sm:inline">
              <Pill tone="border-danger/30 bg-danger/10 text-danger">New</Pill>
            </span>
          ) : null}
          {suppressed ? (
            <span className="hidden shrink-0 sm:inline">
              <Pill tone={TRIAGE_TONE[status]}>
                {TRIAGE_CHOICES.find((c) => c.value === status)?.label ?? status}
              </Pill>
            </span>
          ) : null}
          {vuln.has_fix ? (
            <span className="hidden shrink-0 sm:inline">
              <Pill tone="border-signal/30 bg-signal/10 text-signal">
                <Wrench className="h-3 w-3" strokeWidth={2} />
                Fix
              </Pill>
            </span>
          ) : null}
          {/* Only while collapsed — expanded, the labelled control sits in the
              description toolbar instead. */}
          <span className="shrink-0 group-open:hidden">
            {/* Nested so the responsive rule can't out-specify group-open. */}
            <span className="hidden sm:inline">
              <IssueAction vuln={vuln} scanId={scanId} compact />
            </span>
          </span>
          {vuln.cvss_score != null ? (
            <span className="hidden shrink-0 font-mono text-[11px] text-muted sm:inline">
              CVSS {vuln.cvss_score.toFixed(1)}
            </span>
          ) : null}
          <ChevronDown
            className="h-4 w-4 shrink-0 text-faint transition-transform group-open:rotate-180"
            strokeWidth={2}
          />
        </summary>

        <div className="space-y-4 border-t border-line px-4 py-4">
          {meta.length > 0 ? (
            <dl className="flex flex-wrap gap-x-6 gap-y-2 font-mono text-[11px]">
              {meta.map((m) => (
                <div key={m.k} className="flex items-center gap-1.5">
                  <dt className="text-faint">{m.k}</dt>
                  <dd className="text-muted">{m.v}</dd>
                </div>
              ))}
            </dl>
          ) : null}

          <Section title="Description">
            <Markdown
              text={vuln.description}
              actions={
                <>
                  <IssueAction vuln={vuln} scanId={scanId} />
                  <CopyLinkAction findingId={vuln.id} />
                </>
              }
            />
          </Section>

          {vuln.poc_code ? (
            <Section title="Proof of concept" icon={FileWarning}>
              <CodeBlock text={vuln.poc_code} />
            </Section>
          ) : null}

          <EvidenceSection evidence={vuln.evidence} />

          {vuln.remediation ? (
            <Section title="Remediation" icon={ShieldCheck}>
              <Markdown text={vuln.remediation} />
            </Section>
          ) : null}

          {/* Verdicts are stored against the finding's fingerprint, so they
              carry forward to every future scan of this target. */}
          <div className="border-t border-line pt-3.5">
            <p className="mb-2 font-mono text-[10px] uppercase tracking-wide text-faint">
              Triage
            </p>
            <div className="flex flex-wrap items-center gap-2">
              {TRIAGE_CHOICES.map((choice) => (
                <button
                  key={choice.value}
                  type="button"
                  disabled={triage.isPending || !vuln.fingerprint}
                  onClick={() => triage.mutate(choice.value)}
                  className={cn(
                    "rounded-md border px-2.5 py-1 font-mono text-[11px] transition-colors disabled:opacity-50",
                    choice.value === status
                      ? TRIAGE_TONE[choice.value]
                      : "border-line bg-ink text-faint hover:text-muted"
                  )}
                >
                  {choice.label}
                </button>
              ))}
              <RetestAction vuln={vuln} scanId={scanId} />
              {triage.isPending ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin text-faint" strokeWidth={2} />
              ) : null}
            </div>
            {vuln.retest_outcome ? (
              <p
                className={cn(
                  "mt-2 text-[12px]",
                  vuln.retest_outcome === "fixed" ? "text-signal" : "text-amber"
                )}
              >
                {vuln.retest_outcome === "fixed"
                  ? "Verified fixed — the original exploit was re-run and no longer succeeds"
                  : vuln.retest_outcome === "still_vulnerable"
                    ? "Retested — the exploit still succeeds"
                    : "Retest did not complete; nothing was proven"}
                {vuln.retested_at ? ` on ${formatDate(vuln.retested_at)}` : ""}.
              </p>
            ) : null}
            {!vuln.fingerprint ? (
              <p className="mt-2 text-[12px] text-faint">
                This finding predates fingerprinting and cannot be triaged.
              </p>
            ) : null}
          </div>
        </div>
      </details>
    </Card>
  );
}

/** What was actually observed, so the reader can check the claim themselves.
 *
 *  The most common complaint about AI pentesting is findings nobody can
 *  reproduce. A description is an assertion; the transcript below is the
 *  receipt — and the provenance line says what produced it and when. */
function EvidenceSection({ evidence }: { evidence: Evidence | null }) {
  if (!evidence) return null;

  const provenance = [
    evidence.target_url ? `Target ${evidence.target_url}` : null,
    evidence.commit_sha ? `Commit ${evidence.commit_sha.slice(0, 12)}` : null,
    evidence.model ? `Model ${evidence.model}` : null,
    evidence.observed_at ? `Observed ${formatDate(evidence.observed_at)}` : null,
  ].filter(Boolean) as string[];

  const hasProof = evidence.request || evidence.response || evidence.poc_output;
  if (!hasProof && provenance.length === 0) return null;

  return (
    <Section title="Evidence" icon={BadgeCheck}>
      <div className="space-y-2.5">
        {evidence.request ? (
          <div>
            <p className="mb-1 font-mono text-[10px] text-faint">Request</p>
            <CodeBlock text={evidence.request} />
          </div>
        ) : null}
        {evidence.response ? (
          <div>
            <p className="mb-1 font-mono text-[10px] text-faint">Response</p>
            <CodeBlock text={evidence.response} />
          </div>
        ) : null}
        {evidence.poc_output ? (
          <div>
            <p className="mb-1 font-mono text-[10px] text-faint">Exploit output</p>
            <CodeBlock text={evidence.poc_output} />
          </div>
        ) : null}
        {!hasProof ? (
          <p className="text-[12px] text-faint">
            No transcript was captured for this finding — only its provenance.
          </p>
        ) : null}
        {provenance.length > 0 ? (
          <p className="font-mono text-[11px] leading-relaxed text-faint">
            {provenance.join(" · ")}
          </p>
        ) : null}
      </div>
    </Section>
  );
}

/** Re-runs this finding's proof of concept to prove whether it still works. */
function RetestAction({ vuln, scanId }: { vuln: Vulnerability; scanId: string }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const router = useRouter();

  const retest = useMutation({
    mutationFn: () => api.retestFinding(scanId, vuln.id),
    onSuccess: ({ scan_id }) => {
      queryClient.invalidateQueries({ queryKey: ["scans"] });
      toast.success("Retest started — re-running the original exploit.");
      router.push(`/scans/${scan_id}`);
    },
    onError: (err) =>
      toast.fromError(
        err,
        "Could not start the retest. The target may need a live URL."
      ),
  });

  return (
    <button
      type="button"
      disabled={retest.isPending || !vuln.fingerprint}
      title="Re-run this finding's proof of concept against the live target"
      onClick={() => retest.mutate()}
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border border-line bg-ink px-2.5 py-1",
        "font-mono text-[11px] text-faint transition-colors",
        "hover:border-cyan/40 hover:text-fg disabled:opacity-50"
      )}
    >
      {retest.isPending ? (
        <Loader2 className="h-3 w-3 animate-spin" strokeWidth={2} />
      ) : (
        <RefreshCw className="h-3 w-3" strokeWidth={2} />
      )}
      Verify fix
    </button>
  );
}

const CHIP =
  "inline-flex items-center gap-1.5 rounded-md border border-line bg-ink transition-colors hover:border-cyan/40 hover:text-fg";
const CHIP_SIZE = "px-2 py-1.5 font-mono text-[11px]";
const CHIP_SIZE_COMPACT = "p-1.5";

/** Copies a deep link to this finding, so one result can be handed to a
 *  teammate without telling them to scroll. */
function CopyLinkAction({ findingId }: { findingId: string }) {
  const toast = useToast();
  return (
    <button
      type="button"
      onClick={() => {
        const url = `${window.location.origin}${window.location.pathname}#finding-${findingId}`;
        navigator.clipboard
          .writeText(url)
          .then(() => toast.success("Link to this finding copied."))
          .catch(() => toast.error("Could not copy the link."));
      }}
      className={cn(CHIP, CHIP_SIZE, "text-faint")}
    >
      <Link2 className="h-3.5 w-3.5" strokeWidth={2} />
      Copy link
    </button>
  );
}

/** Opens — or links to — the issue tracking this finding, in whichever
    tracker the organization has configured (GitHub, Jira, or Linear).
    `compact` is the icon-only form shown in the collapsed summary row, where
    there is no space for a label. */
function IssueAction({
  vuln,
  scanId,
  compact,
}: {
  vuln: Vulnerability;
  scanId: string;
  compact?: boolean;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const size = compact ? CHIP_SIZE_COMPACT : CHIP_SIZE;
  // The issue URL is stored against the fingerprint, so the refetch turns the
  // button into a link and a second click can't open a duplicate.
  const issue = useMutation({
    mutationFn: () => api.createFindingIssue(scanId, vuln.id),
    onSuccess: ({ created, tracker, issue_key }) => {
      queryClient.invalidateQueries({ queryKey: ["report", scanId] });
      const where = tracker === "github" ? "GitHub" : tracker === "jira" ? "Jira" : "Linear";
      toast.success(
        created
          ? issue_key
            ? where + " issue " + issue_key + " opened."
            : where + " issue opened."
          : "This finding already has an issue."
      );
    },
    onError: (err) => toast.fromError(err, "Could not create the issue."),
  });

  if (vuln.github_issue_url) {
    return (
      <a
        href={vuln.github_issue_url}
        target="_blank"
        rel="noreferrer noopener"
        title="View the issue tracking this finding"
        // Inside <summary>, a click that reaches the parent toggles the card.
        onClick={(e) => e.stopPropagation()}
        className={cn(CHIP, size, "text-muted")}
      >
        <Github className="h-3.5 w-3.5" strokeWidth={2} />
        {compact ? null : (
          <>
            View {vuln.issue_key ?? "issue"}
            <ExternalLink className="h-3 w-3" strokeWidth={2} />
          </>
        )}
      </a>
    );
  }

  return (
    <button
      type="button"
      disabled={issue.isPending || !vuln.fingerprint}
      title={
        vuln.fingerprint
          ? "File this finding in your issue tracker"
          : "This finding cannot be tracked — it has no fingerprint"
      }
      onClick={(e) => {
        e.stopPropagation();
        e.preventDefault();
        issue.mutate();
      }}
      className={cn(CHIP, size, "text-faint disabled:opacity-50")}
    >
      {issue.isPending ? (
        <Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={2} />
      ) : (
        <Github className="h-3.5 w-3.5" strokeWidth={2} />
      )}
      {compact ? null : "File issue"}
    </button>
  );
}

function Section({
  title,
  icon: Icon,
  children,
}: {
  title: string;
  icon?: typeof ShieldCheck;
  children: React.ReactNode;
}) {
  return (
    <div>
      <p className="mb-1.5 flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wide text-faint">
        {Icon ? <Icon className="h-3.5 w-3.5" strokeWidth={2} /> : null}
        {title}
      </p>
      {children}
    </div>
  );
}
