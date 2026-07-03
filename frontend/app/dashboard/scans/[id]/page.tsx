"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  GitBranch,
  GitCommitHorizontal,
  Clock,
  Cpu,
  Download,
  ChevronDown,
  ShieldCheck,
  Copy,
  Check,
  MapPin,
  Wrench,
} from "lucide-react";
import {
  Card,
  Eyebrow,
  RiskGauge,
  SeverityBadge,
  ScanStatusPill,
  btn,
  cx,
} from "@/components/aegis/kit";
import {
  getScanReport,
  formatDuration,
  type Severity,
  type Vulnerability,
} from "@/lib/mock-data";

const SEV_ORDER: Severity[] = ["critical", "high", "medium", "low"];
const SEV_TEXT: Record<Severity, string> = {
  critical: "text-sev-critical",
  high: "text-sev-high",
  medium: "text-sev-medium",
  low: "text-sev-low",
};
const SEV_BAR: Record<Severity, string> = {
  critical: "bg-sev-critical",
  high: "bg-sev-high",
  medium: "bg-sev-medium",
  low: "bg-sev-low",
};

export default function ScanReportPage() {
  const params = useParams<{ id: string }>();
  const report = getScanReport(params.id);
  const { meta, vulnerabilities } = report;

  const grouped = SEV_ORDER.map((sev) => ({
    sev,
    items: vulnerabilities.filter((v) => v.severity === sev),
  })).filter((g) => g.items.length > 0);

  return (
    <>
      {/* Back */}
      <Link
        href="/dashboard/scans"
        className="mb-5 inline-flex items-center gap-1.5 font-mono text-xs text-muted transition-colors hover:text-violet-soft"
      >
        <ArrowLeft className="h-3.5 w-3.5" />
        Scan History
      </Link>

      {/* Summary header */}
      <Card className="p-6">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-center lg:justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-3">
              <Eyebrow>Scan report</Eyebrow>
              <ScanStatusPill status={meta.status} />
            </div>
            <h1 className="mt-2.5 font-mono text-xl font-semibold text-fg">{meta.repo}</h1>

            <div className="mt-4 flex flex-wrap items-center gap-x-5 gap-y-2 font-mono text-xs text-muted">
              <span className="inline-flex items-center gap-1.5">
                <GitBranch className="h-3.5 w-3.5 text-faint" />
                {meta.branch}
              </span>
              <span className="inline-flex items-center gap-1.5">
                <GitCommitHorizontal className="h-3.5 w-3.5 text-faint" />
                {meta.commit}
              </span>
              <span className="inline-flex items-center gap-1.5">
                <Clock className="h-3.5 w-3.5 text-faint" />
                {meta.startedLabel} · {formatDuration(meta.durationSec)}
              </span>
              <span className="inline-flex items-center gap-1.5">
                <Cpu className="h-3.5 w-3.5 text-faint" />
                {meta.model}
              </span>
              <span className="font-mono text-faint">{meta.id}</span>
            </div>

            {/* Severity summary chips */}
            <div className="mt-5 flex flex-wrap gap-2">
              {SEV_ORDER.map((k) => (
                <span
                  key={k}
                  className="inline-flex items-center gap-2 rounded-lg border border-line bg-raised px-3 py-1.5 font-mono text-xs"
                >
                  <span className={cx("h-1.5 w-1.5 rounded-full", SEV_BAR[k])} />
                  <span className={cx("font-semibold", SEV_TEXT[k])}>
                    {meta.findings[k]}
                  </span>
                  <span className="capitalize text-faint">{k}</span>
                </span>
              ))}
            </div>
          </div>

          {/* Gauge + actions */}
          <div className="flex shrink-0 flex-col items-center gap-4 lg:border-l lg:border-line lg:pl-8">
            <RiskGauge score={meta.riskScore} />
            <button className={cx(btn.ghost, "w-full")}>
              <Download className="h-4 w-4" />
              Export report
            </button>
          </div>
        </div>

        {/* Validation banner — the product's core promise */}
        <div className="mt-6 flex items-center gap-2.5 rounded-lg border border-signal/25 bg-signal/[0.06] px-4 py-3">
          <ShieldCheck className="h-4 w-4 shrink-0 text-signal" />
          <p className="text-sm text-muted">
            <span className="font-semibold text-fg">
              {vulnerabilities.length} findings validated.
            </span>{" "}
            Each exploit was executed and replayed in an isolated sandbox — zero false
            positives by construction.
          </p>
        </div>
      </Card>

      {/* Vulnerabilities grouped by severity */}
      <div className="mt-6 space-y-8">
        {grouped.map((group) => (
          <section key={group.sev}>
            <div className="mb-3 flex items-center gap-3">
              <SeverityBadge severity={group.sev} />
              <span className="font-mono text-xs text-faint">
                {group.items.length} finding{group.items.length > 1 ? "s" : ""}
              </span>
              <span className="h-px flex-1 bg-line" />
            </div>
            <div className="space-y-3">
              {group.items.map((v) => (
                <VulnCard key={v.id} vuln={v} defaultOpen={group.sev === "critical"} />
              ))}
            </div>
          </section>
        ))}
      </div>
    </>
  );
}

/* --------------------------- vulnerability card ------------------------- */

function VulnCard({
  vuln,
  defaultOpen = false,
}: {
  vuln: Vulnerability;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const panelId = `vuln-${vuln.id}`;

  return (
    <Card className="overflow-hidden">
      <button
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
        aria-controls={panelId}
        className="flex w-full items-center gap-4 px-5 py-4 text-left transition-colors hover:bg-surface/60"
      >
        <SeverityBadge severity={vuln.severity} />
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-sm font-medium text-fg">{vuln.title}</h3>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[11px] text-faint">
            <span>{vuln.id}</span>
            <span className="inline-flex items-center gap-1">
              <MapPin className="h-3 w-3" />
              {vuln.location}
            </span>
          </div>
        </div>
        <div className="hidden shrink-0 items-center gap-3 sm:flex">
          <span className="font-mono text-xs text-muted">
            CVSS <span className="font-semibold text-fg">{vuln.cvss.toFixed(1)}</span>
          </span>
          <span className="rounded border border-line bg-raised px-2 py-0.5 font-mono text-[11px] text-muted">
            {vuln.cwe}
          </span>
        </div>
        <ChevronDown
          className={cx(
            "h-4 w-4 shrink-0 text-faint transition-transform",
            open && "rotate-180",
          )}
        />
      </button>

      {open && (
        <div id={panelId} className="border-t border-line px-5 pb-5 pt-4">
          {/* Meta row for small screens */}
          <div className="mb-4 flex flex-wrap items-center gap-2 sm:hidden">
            <span className="font-mono text-xs text-muted">
              CVSS <span className="font-semibold text-fg">{vuln.cvss.toFixed(1)}</span>
            </span>
            <span className="rounded border border-line bg-raised px-2 py-0.5 font-mono text-[11px] text-muted">
              {vuln.cwe}
            </span>
            {vuln.validated && (
              <span className="inline-flex items-center gap-1 font-mono text-[11px] text-signal">
                <ShieldCheck className="h-3 w-3" />
                validated
              </span>
            )}
          </div>

          {/* Description */}
          <Section label="Description">
            <p className="text-sm leading-relaxed text-muted">{vuln.description}</p>
          </Section>

          {/* PoC */}
          <Section label="Proof of concept" className="mt-5">
            <CodeBlock code={vuln.poc} lang={vuln.pocLang} />
          </Section>

          {/* Remediation */}
          <Section label="Remediation" className="mt-5">
            <ol className="space-y-2.5">
              {vuln.remediation.map((step, i) => (
                <li key={i} className="flex gap-3">
                  <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full border border-violet/30 bg-violet/10 font-mono text-[10px] font-semibold text-violet-soft">
                    {i + 1}
                  </span>
                  <span className="text-sm leading-relaxed text-muted">{step}</span>
                </li>
              ))}
            </ol>
          </Section>
        </div>
      )}
    </Card>
  );
}

function Section({
  label,
  children,
  className,
}: {
  label: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={className}>
      <div className="mb-2 flex items-center gap-2">
        {label === "Remediation" && <Wrench className="h-3.5 w-3.5 text-faint" />}
        <Eyebrow>{label}</Eyebrow>
      </div>
      {children}
    </div>
  );
}

function CodeBlock({ code, lang }: { code: string; lang: string }) {
  const [copied, setCopied] = useState(false);

  const onCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 1600);
    } catch {
      /* clipboard unavailable — no-op */
    }
  };

  return (
    <div className="overflow-hidden rounded-lg border border-line bg-[#090C13]">
      <div className="flex items-center justify-between border-b border-line bg-surface/60 px-4 py-2">
        <span className="font-mono text-[11px] uppercase tracking-wider text-faint">
          {lang}
        </span>
        <button
          onClick={onCopy}
          className="inline-flex items-center gap-1.5 font-mono text-[11px] text-muted transition-colors hover:text-fg"
        >
          {copied ? (
            <>
              <Check className="h-3.5 w-3.5 text-signal" />
              Copied
            </>
          ) : (
            <>
              <Copy className="h-3.5 w-3.5" />
              Copy
            </>
          )}
        </button>
      </div>
      <pre className="overflow-x-auto px-4 py-3.5 font-mono text-[12.5px] leading-relaxed text-fg">
        <code>{code}</code>
      </pre>
    </div>
  );
}
