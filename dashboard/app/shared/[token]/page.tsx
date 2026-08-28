"use client";

// The public face of a shared report.
//
// Deliberately outside the (app) route group: there is no session here, and
// no navigation into the rest of the product. A recipient sees exactly one
// report, read-only, until the link expires — and by default without the
// proof-of-concept exploits, which would otherwise be a working recipe
// against the customer's production system.

import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, BadgeCheck, Download, ShieldCheck } from "lucide-react";
import Image from "next/image";
import { useParams } from "next/navigation";
import { useState } from "react";

import { CodeBlock, Markdown } from "@/components/Markdown";
import {
  Card,
  ErrorState,
  SeverityBadge,
  SeverityBar,
  Spinner,
} from "@/components/ui";
import { formatDate, riskBand, riskScore, SEVERITY_ORDER } from "@/lib/format";
import type { ScanReport, Vulnerability } from "@/lib/types";

const BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000/api/v1";

export default function SharedReportPage() {
  const { token } = useParams<{ token: string }>();
  const [downloading, setDownloading] = useState(false);

  // Unauthenticated by design — the token in the path is the credential, so
  // this hits the public endpoint directly rather than the API client.
  const reportQuery = useQuery({
    queryKey: ["shared", token],
    queryFn: async (): Promise<ScanReport> => {
      const res = await fetch(`${BASE_URL}/shared/${token}`, { cache: "no-store" });
      if (!res.ok) throw new Error("expired");
      return res.json();
    },
    retry: false,
  });

  const download = async () => {
    setDownloading(true);
    try {
      const res = await fetch(`${BASE_URL}/shared/${token}/report.pdf`, {
        cache: "no-store",
      });
      if (!res.ok) throw new Error("failed");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = "aegis-report.pdf";
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } finally {
      setDownloading(false);
    }
  };

  return (
    <main className="mx-auto min-h-screen w-full max-w-3xl px-5 py-10">
      <header className="mb-8 flex items-center justify-between gap-4">
        <div className="flex items-center gap-2.5">
          <Image src="/logo.png" alt="" width={28} height={28} priority />
          <div>
            <p className="font-display text-[15px] font-semibold text-fg">
              Penetration test report
            </p>
            <p className="text-[11px] text-faint">Shared securely by Aegis</p>
          </div>
        </div>
        {reportQuery.data ? (
          <button
            type="button"
            onClick={download}
            disabled={downloading}
            className="inline-flex items-center gap-2 rounded-lg border border-line bg-surface px-4 py-2.5 font-display text-[13px] font-semibold text-fg transition-colors hover:border-cyan/40 disabled:opacity-50"
          >
            <Download className="h-4 w-4" strokeWidth={2} />
            {downloading ? "Preparing…" : "Download PDF"}
          </button>
        ) : null}
      </header>

      {reportQuery.isLoading ? (
        <Spinner label="Loading report…" />
      ) : reportQuery.error || !reportQuery.data ? (
        <ErrorState message="This link is not valid, or it has expired. Ask whoever shared it for a new one." />
      ) : (
        <SharedReport report={reportQuery.data} />
      )}

      <footer className="mt-12 border-t border-line pt-5 text-[11px] leading-relaxed text-faint">
        Every finding in this report was confirmed by exploitation against the
        target; candidates that could not be exploited were discarded rather
        than reported. The absence of a finding is not proof that a
        vulnerability does not exist.
      </footer>
    </main>
  );
}

function SharedReport({ report }: { report: ScanReport }) {
  const score = riskScore(report.counts_by_severity);
  const band = riskBand(score);
  const scan = report.scan;

  return (
    <>
      <Card className="mb-6 p-5">
        <h1 className="font-mono text-lg font-semibold text-fg">
          {scan.target_name ?? "Target"}
        </h1>
        <p className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 font-mono text-[11px] text-faint">
          <span className="capitalize">{scan.scan_mode} scan</span>
          <span>·</span>
          <span>Tested {formatDate(scan.started_at ?? scan.created_at)}</span>
          {scan.completed_at ? (
            <>
              <span>·</span>
              <span>Completed {formatDate(scan.completed_at)}</span>
            </>
          ) : null}
        </p>

        <div className="mt-5 flex flex-wrap items-center justify-between gap-4">
          <div className="flex flex-wrap gap-2">
            {SEVERITY_ORDER.map((sev) => {
              const count = report.counts_by_severity[sev] ?? 0;
              if (count === 0) return null;
              return (
                <span
                  key={sev}
                  className="flex items-center gap-2 rounded-lg border border-line bg-ink px-3 py-2"
                >
                  <SeverityBadge severity={sev} />
                  <span className="font-display text-sm font-bold text-fg">{count}</span>
                </span>
              );
            })}
          </div>
          <div className="text-right">
            <span className="block font-mono text-[10px] uppercase tracking-wide text-faint">
              Risk score
            </span>
            <span className="font-display text-2xl font-bold" style={{ color: band.color }}>
              {score}
              <span className="ml-1 text-sm font-medium text-muted">/ 100</span>
            </span>
          </div>
        </div>
        <SeverityBar counts={report.counts_by_severity} className="mt-5" />

        {report.verified_fixed_count > 0 ? (
          <p className="mt-4 flex items-start gap-2 rounded-lg border border-signal/30 bg-signal/[0.07] px-3 py-2.5 text-[12px] leading-relaxed text-signal">
            <BadgeCheck className="mt-0.5 h-4 w-4 shrink-0" strokeWidth={2} />
            {report.verified_fixed_count} finding
            {report.verified_fixed_count === 1 ? " has" : "s have"} been
            remediated and verified by re-running the original proof of concept.
          </p>
        ) : null}
      </Card>

      {report.total === 0 ? (
        <Card className="flex flex-col items-center justify-center px-6 py-16 text-center">
          <span className="mb-4 grid h-12 w-12 place-items-center rounded-xl border border-signal/30 bg-signal/10 text-signal">
            <ShieldCheck className="h-6 w-6" strokeWidth={2} />
          </span>
          <h2 className="font-display text-[15px] font-semibold text-fg">
            No vulnerabilities found
          </h2>
          <p className="mt-1.5 max-w-sm text-[13px] leading-relaxed text-muted">
            The assessment completed and no exploitable vulnerabilities were
            identified in this run.
          </p>
        </Card>
      ) : (
        <div className="space-y-3">
          {report.attack_chains.length > 0 ? (
            <Card className="p-5">
              <h2 className="mb-3 flex items-center gap-2 font-display text-[15px] font-semibold text-fg">
                <AlertTriangle className="h-4 w-4 text-amber" strokeWidth={2} />
                Attack chains
              </h2>
              <ul className="space-y-3">
                {report.attack_chains.map((chain, i) => (
                  <li key={i} className="rounded-lg border border-line bg-ink px-4 py-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <SeverityBadge severity={chain.severity} />
                      <span className="font-display text-[14px] font-semibold text-fg">
                        {chain.title}
                      </span>
                    </div>
                    <p className="mt-2 text-[13px] leading-relaxed text-muted">
                      {chain.narrative}
                    </p>
                  </li>
                ))}
              </ul>
            </Card>
          ) : null}

          {SEVERITY_ORDER.flatMap((sev) =>
            report.vulnerabilities.filter((v) => v.severity === sev)
          ).map((vuln) => (
            <SharedFinding key={vuln.id} vuln={vuln} />
          ))}
        </div>
      )}
    </>
  );
}

function SharedFinding({ vuln }: { vuln: Vulnerability }) {
  return (
    <Card className="overflow-hidden">
      <details className="group">
        <summary className="flex cursor-pointer list-none items-center gap-3 px-4 py-3.5 transition-colors hover:bg-surface/60 [&::-webkit-details-marker]:hidden">
          <SeverityBadge severity={vuln.severity} />
          <span className="min-w-0 flex-1 truncate font-display text-[14px] font-semibold text-fg">
            {vuln.title}
          </span>
          {vuln.retest_outcome === "fixed" ? (
            <BadgeCheck className="h-4 w-4 shrink-0 text-signal" strokeWidth={2} />
          ) : null}
        </summary>
        <div className="space-y-4 border-t border-line px-4 py-4">
          <Markdown text={vuln.description} />
          {vuln.poc_code ? <CodeBlock text={vuln.poc_code} /> : null}
          {vuln.remediation ? (
            <div>
              <p className="mb-1.5 font-mono text-[10px] uppercase tracking-wide text-faint">
                Remediation
              </p>
              <Markdown text={vuln.remediation} />
            </div>
          ) : null}
          {vuln.retest_outcome === "fixed" ? (
            <p className="text-[12px] text-signal">
              Verified fixed
              {vuln.retested_at ? ` on ${formatDate(vuln.retested_at)}` : ""} — the
              original exploit was re-run and no longer succeeds.
            </p>
          ) : null}
        </div>
      </details>
    </Card>
  );
}
