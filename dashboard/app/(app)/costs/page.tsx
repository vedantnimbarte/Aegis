"use client";

// What testing cost this month, and what it bought.
//
// Every figure comes from the engine's own usage report, recorded per scan.
// Showing it is a choice: buyers of a metered product are quietly worried
// about the bill, and no competitor at this price point tells them.

import { useQuery } from "@tanstack/react-query";
import { Receipt, TrendingUp } from "lucide-react";

import {
  Card,
  EmptyState,
  ErrorState,
  PageHeader,
  SkeletonCards,
  SkeletonList,
} from "@/components/ui";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import type { CostSummary, TargetCost } from "@/lib/types";

function money(value: number | null): string {
  if (value == null) return "—";
  return value < 1 ? `$${value.toFixed(3)}` : `$${value.toFixed(2)}`;
}

export default function CostsPage() {
  const costsQuery = useQuery({
    queryKey: ["dashboard", "costs"],
    queryFn: () => api.costSummary(),
  });

  return (
    <>
      <PageHeader
        title="Costs"
        subtitle="What this month's testing cost, straight from the engine's usage report."
      />

      {costsQuery.isLoading ? (
        <SkeletonCards count={3} />
      ) : costsQuery.error || !costsQuery.data ? (
        <ErrorState message="Could not load cost reporting." />
      ) : (
        <Costs summary={costsQuery.data} />
      )}
    </>
  );
}

function Costs({ summary }: { summary: CostSummary }) {
  if (summary.total_scans === 0) {
    return (
      <EmptyState icon={Receipt} title="No spend this period">
        Costs appear here once a scan has completed. Nothing has run since{" "}
        {formatDate(summary.period_start)}.
      </EmptyState>
    );
  }

  return (
    <>
      <div className="grid grid-cols-2 gap-3.5 lg:grid-cols-4">
        <Stat label="Spend this month" value={money(summary.total_cost_usd)} />
        <Stat label="Scans" value={summary.total_scans.toLocaleString()} />
        <Stat label="Cost per scan" value={money(summary.cost_per_scan)} />
        {/* The number that actually compares one security tool with another. */}
        <Stat
          label="Cost per validated finding"
          value={money(summary.cost_per_validated_finding)}
          hint={`${summary.validated_findings} still open`}
          accent="#22D3EE"
        />
      </div>

      {Object.keys(summary.forecast_by_mode).length > 0 ? (
        <Card className="mt-3.5 flex flex-wrap items-center gap-x-8 gap-y-2 px-5 py-3.5">
          <span className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-wide text-faint">
            <TrendingUp className="h-3.5 w-3.5" strokeWidth={2} />
            Expected next scan
          </span>
          {Object.entries(summary.forecast_by_mode).map(([mode, cost]) => (
            <span key={mode} className="text-[13px] text-muted">
              <span className="capitalize">{mode}</span>{" "}
              <span className="font-mono text-fg">{money(cost)}</span>
            </span>
          ))}
          <span className="text-[11px] text-faint">
            From your own runs, not a generic price list.
          </span>
        </Card>
      ) : null}

      <section className="mt-10">
        <h2 className="mb-4 font-display text-[15px] font-semibold text-fg">By target</h2>
        {summary.by_target.length === 0 ? (
          <SkeletonList rows={2} />
        ) : (
          <Card className="overflow-x-auto">
            <table className="w-full min-w-[560px] text-left">
              <thead>
                <tr className="border-b border-line font-mono text-[10px] uppercase tracking-wide text-faint">
                  <th className="px-4 py-3 font-normal">Target</th>
                  <th className="px-4 py-3 font-normal">Scans</th>
                  <th className="px-4 py-3 font-normal">Spend</th>
                  <th className="px-4 py-3 font-normal">Open findings</th>
                  <th className="px-4 py-3 font-normal">Per finding</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {summary.by_target.map((row) => (
                  <TargetRow key={row.target_id} row={row} />
                ))}
              </tbody>
            </table>
          </Card>
        )}
      </section>
    </>
  );
}

function TargetRow({ row }: { row: TargetCost }) {
  return (
    <tr className="text-[13px]">
      <td className="px-4 py-3 font-mono text-fg">{row.target_name}</td>
      <td className="px-4 py-3 font-mono text-muted">{row.scans}</td>
      <td className="px-4 py-3 font-mono text-fg">{money(row.cost_usd)}</td>
      <td className="px-4 py-3 font-mono text-muted">{row.validated_findings}</td>
      <td className="px-4 py-3 font-mono text-muted">
        {money(row.cost_per_validated_finding)}
      </td>
    </tr>
  );
}

function Stat({
  label,
  value,
  hint,
  accent,
}: {
  label: string;
  value: string;
  hint?: string;
  accent?: string;
}) {
  return (
    <Card className="p-4">
      <p className="mb-3 font-mono text-[10px] uppercase tracking-[0.12em] text-faint">
        {label}
      </p>
      <p
        className="font-display text-2xl font-bold text-fg"
        style={accent ? { color: accent } : undefined}
      >
        {value}
      </p>
      {hint ? <p className="mt-1 text-[11px] text-muted">{hint}</p> : null}
    </Card>
  );
}
