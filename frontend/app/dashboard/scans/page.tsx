import Link from "next/link";
import { ArrowUpRight, Clock } from "lucide-react";
import {
  Card,
  Eyebrow,
  FindingsBadge,
  ScanStatusPill,
  cx,
} from "@/components/aegis/kit";
import { scans, formatDuration } from "@/lib/mock-data";

const FILTERS = ["All", "Completed", "Running", "Pending", "Failed"] as const;

export default function ScanHistoryPage() {
  return (
    <>
      {/* Header */}
      <header className="mb-6">
        <Eyebrow className="mb-2">{scans.length} scans · last 7 days</Eyebrow>
        <h1 className="font-display text-2xl font-semibold tracking-tight text-fg">
          Scan History
        </h1>
        <p className="mt-1.5 text-sm text-muted">
          Every run Aegis has executed against your repositories.
        </p>
      </header>

      {/* Filter chips (visual for the MVP) */}
      <div className="mb-4 flex flex-wrap gap-2">
        {FILTERS.map((f, i) => (
          <button
            key={f}
            className={cx(
              "rounded-full border px-3 py-1.5 font-mono text-xs transition-colors",
              i === 0
                ? "border-violet/40 bg-violet/10 text-violet-soft"
                : "border-line bg-surface/60 text-muted hover:border-violet/40 hover:text-fg",
            )}
          >
            {f}
          </button>
        ))}
      </div>

      {/* Table */}
      <Card className="overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[820px] border-collapse text-left">
            <thead>
              <tr className="border-b border-line">
                {["Started", "Repository", "Duration", "Findings", "Status", ""].map(
                  (h) => (
                    <th
                      key={h}
                      className="px-5 py-3.5 font-mono text-[10px] font-medium uppercase tracking-[0.15em] text-faint"
                    >
                      {h}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {scans.map((scan) => {
                const done = scan.status === "completed";
                return (
                  <tr
                    key={scan.id}
                    className={cx(
                      "border-b border-line/60 transition-colors last:border-0 hover:bg-surface/60",
                      scan.status === "running" && "bg-violet/[0.03]",
                    )}
                  >
                    {/* Started */}
                    <td className="whitespace-nowrap px-5 py-4">
                      <div className="text-sm text-fg">{scan.dateLabel}</div>
                      <div className="mt-0.5 flex items-center gap-1 font-mono text-[11px] text-faint">
                        <Clock className="h-3 w-3" />
                        {scan.timeLabel}
                      </div>
                    </td>

                    {/* Repository */}
                    <td className="px-5 py-4">
                      <div className="font-mono text-sm text-fg">{scan.repo}</div>
                      <div className="mt-0.5 font-mono text-[11px] text-faint">
                        {scan.branch} · {scan.commit}
                      </div>
                    </td>

                    {/* Duration */}
                    <td className="whitespace-nowrap px-5 py-4 font-mono text-sm text-muted">
                      {scan.status === "running" ? (
                        <span className="text-violet-soft">running…</span>
                      ) : (
                        formatDuration(scan.durationSec)
                      )}
                    </td>

                    {/* Findings */}
                    <td className="whitespace-nowrap px-5 py-4">
                      {scan.status === "completed" ? (
                        <FindingsBadge counts={scan.findings} />
                      ) : (
                        <span className="font-mono text-xs text-faint">—</span>
                      )}
                    </td>

                    {/* Status */}
                    <td className="whitespace-nowrap px-5 py-4">
                      <ScanStatusPill status={scan.status} />
                    </td>

                    {/* Action */}
                    <td className="whitespace-nowrap px-5 py-4 text-right">
                      {done ? (
                        <Link
                          href={`/dashboard/scans/${scan.id}`}
                          className="inline-flex items-center gap-1.5 rounded-md border border-line bg-raised px-3 py-1.5 font-mono text-xs text-muted transition-colors hover:border-violet/40 hover:text-fg"
                        >
                          View Report
                          <ArrowUpRight className="h-3.5 w-3.5" />
                        </Link>
                      ) : (
                        <span className="font-mono text-[11px] text-faint">
                          {scan.status === "failed" ? "No report" : "In progress"}
                        </span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </Card>
    </>
  );
}
