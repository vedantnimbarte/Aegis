/* -------------------------------------------------------------------------- */
/*  components/aegis/kit.tsx                                                    */
/*  Shared, presentational building blocks for the Aegis console. Pure — no    */
/*  hooks — so they compose freely into both server and client pages.          */
/* -------------------------------------------------------------------------- */

import type { HTMLAttributes, ReactNode } from "react";
import { ShieldHalf } from "lucide-react";
import type {
  Severity,
  ScanStatus,
  RepoStatus,
  SeverityCounts,
} from "@/lib/mock-data";
import { totalFindings } from "@/lib/mock-data";

export function cx(...parts: (string | false | null | undefined)[]): string {
  return parts.filter(Boolean).join(" ");
}

/** Reusable button treatments, matched to the landing page's primary CTA. */
export const btn = {
  primary:
    "inline-flex items-center justify-center gap-2 rounded-lg bg-violet px-4 py-2.5 font-display text-sm font-semibold text-white shadow-lg shadow-violet/25 transition-all hover:bg-violet-soft hover:shadow-violet/40 focus-visible:outline-violet-soft disabled:cursor-not-allowed disabled:opacity-50",
  ghost:
    "inline-flex items-center justify-center gap-2 rounded-lg border border-line bg-surface/60 px-4 py-2.5 font-display text-sm font-medium text-muted transition-colors hover:border-violet/40 hover:text-fg",
  subtle:
    "inline-flex items-center justify-center gap-1.5 rounded-md border border-line bg-raised px-3 py-1.5 font-mono text-xs text-muted transition-colors hover:border-violet/40 hover:text-fg",
};

export function Card({
  className,
  children,
  ...rest
}: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cx("rounded-xl border border-line bg-surface/40", className)}
      {...rest}
    >
      {children}
    </div>
  );
}

export function Eyebrow({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <p
      className={cx(
        "font-mono text-[11px] uppercase tracking-[0.2em] text-faint",
        className,
      )}
    >
      {children}
    </p>
  );
}

export function AegisMark({ size = 36 }: { size?: number }) {
  return (
    <span
      className="grid place-items-center rounded-lg border border-violet/40 bg-violet/10 text-violet-soft"
      style={{ width: size, height: size }}
    >
      <ShieldHalf style={{ width: size * 0.52, height: size * 0.52 }} strokeWidth={2} />
    </span>
  );
}

/* ------------------------------ severity -------------------------------- */

const SEV: Record<Severity, { label: string; cls: string; dot: string }> = {
  critical: {
    label: "Critical",
    cls: "text-sev-critical bg-sev-critical/10 border-sev-critical/25",
    dot: "bg-sev-critical",
  },
  high: {
    label: "High",
    cls: "text-sev-high bg-sev-high/10 border-sev-high/25",
    dot: "bg-sev-high",
  },
  medium: {
    label: "Medium",
    cls: "text-sev-medium bg-sev-medium/10 border-sev-medium/25",
    dot: "bg-sev-medium",
  },
  low: {
    label: "Low",
    cls: "text-sev-low bg-sev-low/10 border-sev-low/25",
    dot: "bg-sev-low",
  },
};

const SEV_ORDER: Severity[] = ["critical", "high", "medium", "low"];

export function SeverityBadge({
  severity,
  className,
}: {
  severity: Severity;
  className?: string;
}) {
  const s = SEV[severity];
  return (
    <span
      className={cx(
        "inline-flex items-center gap-1.5 rounded-md border px-2 py-1 font-mono text-[11px] font-medium uppercase tracking-wider",
        s.cls,
        className,
      )}
    >
      <span className={cx("h-1.5 w-1.5 rounded-full", s.dot)} />
      {s.label}
    </span>
  );
}

/** Colored count badge: total, tinted by the worst severity present. */
export function FindingsBadge({ counts }: { counts: SeverityCounts }) {
  const total = totalFindings(counts);
  if (total === 0) {
    return (
      <span className="inline-flex items-center gap-1.5 font-mono text-xs text-signal">
        <span className="h-1.5 w-1.5 rounded-full bg-signal" />
        Clean
      </span>
    );
  }
  const worst = SEV_ORDER.find((k) => counts[k] > 0)!;
  return (
    <span className="inline-flex items-center gap-2">
      <span
        className={cx(
          "min-w-[1.75rem] rounded-md border px-1.5 py-0.5 text-center font-mono text-xs font-semibold",
          SEV[worst].cls,
        )}
      >
        {total}
      </span>
      <span className="hidden items-center gap-2 sm:flex">
        {SEV_ORDER.filter((k) => counts[k] > 0).map((k) => (
          <span
            key={k}
            title={`${counts[k]} ${k}`}
            className="inline-flex items-center gap-1 font-mono text-[11px] text-faint"
          >
            <span className={cx("h-1.5 w-1.5 rounded-full", SEV[k].dot)} />
            {counts[k]}
          </span>
        ))}
      </span>
    </span>
  );
}

/* ------------------------------ statuses -------------------------------- */

const SCAN_STATUS: Record<
  ScanStatus,
  { label: string; text: string; dot: string; pulse: boolean }
> = {
  pending: { label: "Pending", text: "text-faint", dot: "bg-faint", pulse: false },
  running: {
    label: "Running",
    text: "text-violet-soft",
    dot: "bg-violet-soft",
    pulse: true,
  },
  completed: { label: "Completed", text: "text-signal", dot: "bg-signal", pulse: false },
  failed: { label: "Failed", text: "text-danger", dot: "bg-danger", pulse: false },
};

export function ScanStatusPill({ status }: { status: ScanStatus }) {
  const s = SCAN_STATUS[status];
  return (
    <span
      className={cx(
        "inline-flex items-center gap-2 rounded-full border border-line bg-raised px-2.5 py-1 font-mono text-[11px] font-medium",
        s.text,
      )}
    >
      <span
        className={cx(
          "h-1.5 w-1.5 rounded-full",
          s.dot,
          s.pulse && "motion-safe:animate-pulse-dot",
        )}
      />
      {s.label}
    </span>
  );
}

const REPO_STATUS: Record<
  RepoStatus,
  { label: string; text: string; dot: string; pulse: boolean }
> = {
  protected: { label: "Protected", text: "text-signal", dot: "bg-signal", pulse: false },
  at_risk: { label: "At risk", text: "text-sev-high", dot: "bg-sev-high", pulse: false },
  scanning: {
    label: "Scanning",
    text: "text-violet-soft",
    dot: "bg-violet-soft",
    pulse: true,
  },
  never_scanned: {
    label: "Not scanned",
    text: "text-faint",
    dot: "bg-faint",
    pulse: false,
  },
};

export function RepoStatusPill({ status }: { status: RepoStatus }) {
  const s = REPO_STATUS[status];
  return (
    <span
      className={cx(
        "inline-flex items-center gap-2 rounded-full border border-line bg-raised px-2.5 py-1 font-mono text-[11px] font-medium",
        s.text,
      )}
    >
      <span
        className={cx(
          "h-1.5 w-1.5 rounded-full",
          s.dot,
          s.pulse && "motion-safe:animate-pulse-dot",
        )}
      />
      {s.label}
    </span>
  );
}

/* ---------------------------- risk gauge -------------------------------- */

function riskBand(score: number): { hex: string; grade: string; label: string } {
  if (score >= 70) return { hex: "#FB5C6B", grade: "F", label: "Critical exposure" };
  if (score >= 40) return { hex: "#F5B451", grade: "C", label: "Elevated" };
  if (score >= 15) return { hex: "#4ADE80", grade: "B", label: "Low" };
  return { hex: "#4ADE80", grade: "A", label: "Hardened" };
}

/** Radial risk gauge — the console's signature stat. A 270° arc, 0–100. */
export function RiskGauge({ score, size = 148 }: { score: number; size?: number }) {
  const clamped = Math.max(0, Math.min(100, score));
  const band = riskBand(clamped);
  const stroke = 10;
  const r = (size - stroke) / 2 - 2;
  const c = size / 2;
  const circ = 2 * Math.PI * r;
  const arc = 0.75 * circ; // 270° sweep, gap at the bottom
  const value = (clamped / 100) * arc;

  return (
    <div className="relative inline-grid place-items-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="block">
        <g transform={`rotate(135 ${c} ${c})`} fill="none" strokeLinecap="round">
          <circle
            cx={c}
            cy={c}
            r={r}
            stroke="#141926"
            strokeWidth={stroke}
            strokeDasharray={`${arc} ${circ}`}
          />
          <circle
            cx={c}
            cy={c}
            r={r}
            stroke={band.hex}
            strokeWidth={stroke}
            strokeDasharray={`${value} ${circ}`}
            style={{ filter: `drop-shadow(0 0 6px ${band.hex}66)` }}
          />
        </g>
      </svg>
      <div className="absolute inset-0 grid place-items-center text-center">
        <div>
          <div
            className="font-display text-3xl font-semibold leading-none"
            style={{ color: band.hex }}
          >
            {clamped}
          </div>
          <div className="mt-1 font-mono text-[10px] uppercase tracking-widest text-faint">
            risk · {band.grade}
          </div>
        </div>
      </div>
    </div>
  );
}

export { riskBand };
