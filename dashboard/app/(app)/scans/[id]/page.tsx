"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ArrowLeft,
  Check,
  ChevronDown,
  Circle,
  Download,
  ExternalLink,
  Github,
  GitPullRequest,
  Radar,
  ShieldCheck,
  XCircle,
  FileWarning,
  Loader2,
  AlertTriangle,
  Wrench,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMemo } from "react";

import { CodeBlock, Markdown } from "@/components/Markdown";
import {
  Button,
  Card,
  cn,
  ErrorState,
  Pill,
  SeverityBadge,
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
  ProgressStep,
  TriageStatus,
  Scan,
  ScanReport,
  Severity,
  Vulnerability,
} from "@/lib/types";

export default function ScanDetailPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();

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

  const reposQuery = useQuery({ queryKey: ["repos"], queryFn: api.listRepos });
  const repoName = useMemo(() => {
    const r = (reposQuery.data ?? []).find((r) => r.id === scan?.repository_id);
    return r?.name;
  }, [reposQuery.data, scan?.repository_id]);

  const cancel = useMutation({
    mutationFn: () => api.cancelScan(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["scan", id] }),
  });

  const download = useMutation({
    mutationFn: () => api.getReportPdf(id),
    onSuccess: (blob) => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `aegis-report-${id}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    },
  });

  if (scanQuery.isLoading) return <Spinner label="Loading scan…" />;
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
              {repoName ?? "Repository"}
            </h1>
            <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[11px] text-faint">
              <span className="capitalize">{scan.scan_mode} scan</span>
              <span>·</span>
              <span>Started {formatDate(scan.started_at ?? scan.created_at)}</span>
              <span>·</span>
              <span>{formatDuration(scan.started_at, scan.completed_at)}</span>
            </p>
          </div>
        </div>
        <div className="flex items-center gap-3">
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
            <Button
              variant="secondary"
              icon={Download}
              loading={download.isPending}
              onClick={() => download.mutate()}
            >
              Export PDF
            </Button>
          ) : null}
          <StatusBadge status={scan.status} />
        </div>
      </div>

      {download.error ? (
        <div className="mb-6">
          <ErrorState message="Could not export the PDF. Please try again." />
        </div>
      ) : null}

      {scan.custom_instructions ? (
        <Card className="mb-6 px-4 py-3">
          <p className="font-mono text-[10px] uppercase tracking-wide text-faint">Instructions</p>
          <p className="mt-1 text-[13px] leading-relaxed text-muted">{scan.custom_instructions}</p>
        </Card>
      ) : null}

      {cancel.error ? (
        <div className="mb-6">
          <ErrorState message="Could not cancel this scan. It may have just finished." />
        </div>
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
              Model calls <span className="font-mono text-fg">{scan.llm_requests}</span>
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
                <p className="font-mono text-[13px] text-fg">{progress.llm_requests}</p>
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
      <Card className="mb-6 flex flex-col gap-5 p-5 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-wrap gap-2">
          {SEVERITY_ORDER.map((sev) => {
            const count = report.counts_by_severity[sev] ?? 0;
            if (count === 0) return null;
            return (
              <div key={sev} className="flex items-center gap-2 rounded-lg border border-line bg-ink px-3 py-2">
                <SeverityBadge severity={sev} />
                <span className="font-display text-sm font-bold text-fg">{count}</span>
              </div>
            );
          })}
        </div>
        <div className="flex items-center gap-3 sm:flex-col sm:items-end">
          <span className="font-mono text-[10px] uppercase tracking-wide text-faint">Risk score</span>
          <span className="font-display text-3xl font-bold" style={{ color: band.color }}>
            {score}
            <span className="ml-1 text-sm font-medium text-muted">/ 100</span>
          </span>
        </div>
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
          {report.suppressed_count > 0 ? (
            <span className="text-[13px] text-muted">
              · {report.suppressed_count} triaged away
            </span>
          ) : null}
        </Card>
      ) : null}

      <AutofixCard report={report} />

      {/* Findings grouped by severity */}
      <div className="space-y-3">
        {SEVERITY_ORDER.flatMap((sev) =>
          report.vulnerabilities.filter((v) => v.severity === sev)
        ).map((vuln) => (
          <VulnerabilityCard key={vuln.id} vuln={vuln} scanId={report.scan.id} />
        ))}
      </div>
    </>
  );
}

/* -------------------------------------------------------------------------- */
function AutofixCard({ report }: { report: ScanReport }) {
  const queryClient = useQueryClient();
  const scan = report.scan;

  const autofix = useMutation({
    mutationFn: () => api.generateFixPr(scan.id),
    onSuccess: ({ pull_request_url }) => {
      queryClient.invalidateQueries({ queryKey: ["scan", scan.id] });
      queryClient.invalidateQueries({ queryKey: ["report", scan.id] });
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

function VulnerabilityCard({ vuln, scanId }: { vuln: Vulnerability; scanId: string }) {
  const queryClient = useQueryClient();
  const triage = useMutation({
    mutationFn: (status: TriageStatus) =>
      api.triageFinding(scanId, vuln.id, { status }),
    // Refetch the report so the diff/suppressed counts stay in step.
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["report", scanId] }),
  });

  const status = vuln.triage_status;
  const suppressed = status !== "open";
  const meta: { k: string; v: string }[] = [];
  if (vuln.cvss_score != null) meta.push({ k: "CVSS", v: vuln.cvss_score.toFixed(1) });
  if (vuln.owasp_category) meta.push({ k: "Class", v: vuln.owasp_category });
  if (vuln.file_path) meta.push({ k: "Location", v: vuln.file_path });

  return (
    <Card className="overflow-hidden">
      <details className="group">
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
              actions={<IssueAction vuln={vuln} scanId={scanId} />}
            />
          </Section>

          {vuln.poc_code ? (
            <Section title="Proof of concept" icon={FileWarning}>
              <CodeBlock text={vuln.poc_code} />
            </Section>
          ) : null}

          {vuln.remediation ? (
            <Section title="Remediation" icon={ShieldCheck}>
              <Markdown text={vuln.remediation} />
            </Section>
          ) : null}

          {/* Verdicts are stored against the finding's fingerprint, so they
              carry forward to every future scan of this repository. */}
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
              {triage.isPending ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin text-faint" strokeWidth={2} />
              ) : null}
            </div>
            {!vuln.fingerprint ? (
              <p className="mt-2 text-[12px] text-faint">
                This finding predates fingerprinting and cannot be triaged.
              </p>
            ) : null}
            {triage.error ? (
              <p className="mt-2 text-[12px] text-danger">Could not save that verdict.</p>
            ) : null}
          </div>
        </div>
      </details>
    </Card>
  );
}

/** Opens — or links to — the GitHub issue tracking this finding.
    `compact` is the icon-only form shown in the collapsed summary row, where
    there is no space for a label or an error line. */
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
  // The issue URL is stored against the fingerprint, so the refetch turns the
  // button into a link and a second click can't open a duplicate.
  const issue = useMutation({
    mutationFn: () => api.createFindingIssue(scanId, vuln.id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["report", scanId] }),
  });

  const chip =
    "inline-flex items-center gap-1.5 rounded-md border border-line bg-ink transition-colors hover:border-cyan/40 hover:text-fg";
  const size = compact ? "p-1.5" : "px-2 py-1.5 font-mono text-[11px]";
  const failed = issue.error
    ? issue.error instanceof ApiError
      ? issue.error.message
      : "Could not create the issue."
    : null;

  if (vuln.github_issue_url) {
    return (
      <a
        href={vuln.github_issue_url}
        target="_blank"
        rel="noreferrer noopener"
        title="View the GitHub issue for this finding"
        // Inside <summary>, a click that reaches the parent toggles the card.
        onClick={(e) => e.stopPropagation()}
        className={cn(chip, size, "text-muted")}
      >
        <Github className="h-3.5 w-3.5" strokeWidth={2} />
        {compact ? null : (
          <>
            View GitHub issue
            <ExternalLink className="h-3 w-3" strokeWidth={2} />
          </>
        )}
      </a>
    );
  }

  return (
    <>
      <button
        type="button"
        disabled={issue.isPending || !vuln.fingerprint}
        title={failed ?? "Create a GitHub issue for this finding"}
        onClick={(e) => {
          e.stopPropagation();
          e.preventDefault();
          issue.mutate();
        }}
        className={cn(
          chip,
          size,
          failed ? "border-danger/40 text-danger" : "text-faint",
          "disabled:opacity-50"
        )}
      >
        {issue.isPending ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" strokeWidth={2} />
        ) : (
          <Github className="h-3.5 w-3.5" strokeWidth={2} />
        )}
        {compact ? null : "Create GitHub issue"}
      </button>
      {failed && !compact ? (
        // `order-last` + `w-full` drop the reason onto its own line below
        // the whole toolbar, rather than wrapping the icons past it.
        <p className="order-last w-full text-[12px] text-danger">{failed}</p>
      ) : null}
    </>
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
