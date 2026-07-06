"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import {
  ArrowLeft,
  ChevronDown,
  Download,
  Radar,
  ShieldCheck,
  FileWarning,
  Loader2,
  AlertTriangle,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useMemo } from "react";

import {
  Button,
  Card,
  ErrorState,
  SeverityBadge,
  Spinner,
  StatusBadge,
} from "@/components/ui";
import { api } from "@/lib/api";
import {
  formatDate,
  formatDuration,
  riskBand,
  riskScore,
  SEVERITY_ORDER,
} from "@/lib/format";
import type { Scan, ScanReport, Severity, Vulnerability } from "@/lib/types";

export default function ScanDetailPage() {
  const { id } = useParams<{ id: string }>();

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

      {/* Body by status */}
      {scan.status === "pending" || scan.status === "running" ? (
        <InProgress scan={scan} />
      ) : scan.status === "failed" ? (
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
function InProgress({ scan }: { scan: Scan }) {
  return (
    <Card className="flex flex-col items-center justify-center px-6 py-16 text-center">
      <span className="mb-4 grid h-12 w-12 place-items-center rounded-xl border border-cyan/30 bg-cyan/10 text-cyan-soft">
        <Loader2 className="h-6 w-6 animate-spin" strokeWidth={2} />
      </span>
      <h3 className="font-display text-[15px] font-semibold text-fg">
        {scan.status === "pending" ? "Queued for scanning" : "Pentest in progress"}
      </h3>
      <p className="mt-1.5 max-w-sm text-[13px] leading-relaxed text-muted">
        Aegis is cloning the repository into an isolated sandbox and running autonomous agents
        against it. This page updates automatically.
      </p>
    </Card>
  );
}

function FailedState({ scan }: { scan: Scan }) {
  return (
    <Card className="px-5 py-6">
      <div className="flex items-start gap-3">
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-danger/30 bg-danger/10 text-danger">
          <AlertTriangle className="h-4 w-4" strokeWidth={2} />
        </span>
        <div>
          <h3 className="font-display text-[15px] font-semibold text-fg">Scan failed</h3>
          <p className="mt-1.5 text-[13px] leading-relaxed text-muted">
            {scan.error_message || "The scan did not complete. Please try launching it again."}
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

      {/* Findings grouped by severity */}
      <div className="space-y-3">
        {SEVERITY_ORDER.flatMap((sev) =>
          report.vulnerabilities.filter((v) => v.severity === sev)
        ).map((vuln) => (
          <VulnerabilityCard key={vuln.id} vuln={vuln} />
        ))}
      </div>
    </>
  );
}

/* -------------------------------------------------------------------------- */
function VulnerabilityCard({ vuln }: { vuln: Vulnerability }) {
  const meta: { k: string; v: string }[] = [];
  if (vuln.cvss_score != null) meta.push({ k: "CVSS", v: vuln.cvss_score.toFixed(1) });
  if (vuln.owasp_category) meta.push({ k: "Class", v: vuln.owasp_category });
  if (vuln.file_path) meta.push({ k: "Location", v: vuln.file_path });

  return (
    <Card className="overflow-hidden">
      <details className="group">
        <summary className="flex cursor-pointer list-none items-center gap-3 px-4 py-3.5 transition-colors hover:bg-surface/60 [&::-webkit-details-marker]:hidden">
          <SeverityBadge severity={vuln.severity} />
          <span className="min-w-0 flex-1 truncate font-display text-[14px] font-semibold text-fg">
            {vuln.title}
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
            <Prose text={vuln.description} />
          </Section>

          {vuln.poc_code ? (
            <Section title="Proof of concept" icon={FileWarning}>
              <CodeBlock text={vuln.poc_code} />
            </Section>
          ) : null}

          {vuln.remediation ? (
            <Section title="Remediation" icon={ShieldCheck}>
              <Prose text={vuln.remediation} />
            </Section>
          ) : null}
        </div>
      </details>
    </Card>
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

/** Renders text with paragraphs and fenced code blocks lightly formatted. */
function Prose({ text }: { text: string }) {
  const blocks = text.split(/```/);
  return (
    <div className="space-y-2.5 text-[13px] leading-relaxed text-muted">
      {blocks.map((block, i) =>
        i % 2 === 1 ? (
          <CodeBlock key={i} text={block.replace(/^\w*\n/, "").trim()} />
        ) : (
          block
            .trim()
            .split(/\n{2,}/)
            .filter(Boolean)
            .map((para, j) => (
              <p key={`${i}-${j}`} className="whitespace-pre-wrap">
                {para}
              </p>
            ))
        )
      )}
    </div>
  );
}

function CodeBlock({ text }: { text: string }) {
  return (
    <pre className="overflow-x-auto rounded-lg border border-line bg-obsidian px-3.5 py-3 font-mono text-[12px] leading-relaxed text-muted">
      <code>{text}</code>
    </pre>
  );
}
