// Small shared UI primitives, styled to match the Aegis design system.
import { Loader2, type LucideIcon } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";

import { SEVERITY_META, STATUS_META } from "@/lib/format";
import type { ScanStatus, Severity } from "@/lib/types";

/* -------------------------------------------------------------------------- */
export function cn(...parts: Array<string | false | null | undefined>): string {
  return parts.filter(Boolean).join(" ");
}

/* -------------------------------------------------------------------------- */
type ButtonVariant = "primary" | "secondary" | "ghost" | "danger";

const BUTTON_VARIANTS: Record<ButtonVariant, string> = {
  primary:
    "bg-cyan text-obsidian shadow-lg shadow-cyan/20 hover:bg-cyan-soft hover:shadow-cyan/30",
  secondary: "border border-line bg-surface/80 text-fg hover:border-cyan/40 hover:bg-surface",
  ghost: "text-muted hover:bg-surface/70 hover:text-fg",
  danger: "border border-danger/30 bg-danger/10 text-danger hover:bg-danger/20",
};

export function Button({
  variant = "primary",
  loading,
  icon: Icon,
  children,
  className,
  disabled,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: ButtonVariant;
  loading?: boolean;
  icon?: LucideIcon;
}) {
  return (
    <button
      {...props}
      disabled={disabled || loading}
      className={cn(
        "inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2.5 font-display text-[13px] font-semibold transition-all disabled:cursor-not-allowed disabled:opacity-60",
        BUTTON_VARIANTS[variant],
        className
      )}
    >
      {loading ? (
        <Loader2 className="h-4 w-4 animate-spin" strokeWidth={2} />
      ) : Icon ? (
        <Icon className="h-4 w-4" strokeWidth={2} />
      ) : null}
      {children}
    </button>
  );
}

/* -------------------------------------------------------------------------- */
export function Card({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("rounded-xl border border-line bg-surface/40", className)}>
      {children}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
export function Pill({ tone, children }: { tone: string; children: ReactNode }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-md border px-2 py-1 font-mono text-[11px] font-medium",
        tone
      )}
    >
      {children}
    </span>
  );
}

export function SeverityBadge({ severity }: { severity: Severity }) {
  const meta = SEVERITY_META[severity];
  return (
    <Pill tone={meta.pill}>
      <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: meta.dot }} />
      {meta.label}
    </Pill>
  );
}

export function StatusBadge({ status }: { status: ScanStatus }) {
  const meta = STATUS_META[status];
  return (
    <Pill tone={meta.pill}>
      <span
        className={cn(
          "h-1.5 w-1.5 rounded-full",
          status === "running" && "motion-safe:animate-pulse-dot"
        )}
        style={{ backgroundColor: meta.dot }}
      />
      {meta.label}
    </Pill>
  );
}

/* -------------------------------------------------------------------------- */
export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center justify-center gap-2.5 py-16 text-muted">
      <Loader2 className="h-4 w-4 animate-spin" strokeWidth={2} />
      {label ? <span className="text-[13px]">{label}</span> : null}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
export function EmptyState({
  icon: Icon,
  title,
  children,
  action,
}: {
  icon: LucideIcon;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-line bg-surface/30 px-6 py-14 text-center">
      <span className="mb-4 grid h-11 w-11 place-items-center rounded-xl border border-line bg-ink text-cyan-soft">
        <Icon className="h-5 w-5" strokeWidth={1.75} />
      </span>
      <h3 className="font-display text-[15px] font-semibold text-fg">{title}</h3>
      {children ? (
        <p className="mt-1.5 max-w-sm text-[13px] leading-relaxed text-muted">{children}</p>
      ) : null}
      {action ? <div className="mt-5">{action}</div> : null}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
export function ErrorState({ message }: { message: string }) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-danger/30 bg-danger/[0.06] px-5 py-4 text-[13px] text-danger">
      {message}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
export function PageHeader({
  title,
  subtitle,
  action,
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
}) {
  return (
    <div className="mb-8 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h1 className="font-display text-2xl font-bold tracking-[-0.01em] text-fg">{title}</h1>
        {subtitle ? <p className="mt-1 text-[13px] text-muted">{subtitle}</p> : null}
      </div>
      {action ? <div className="shrink-0">{action}</div> : null}
    </div>
  );
}
