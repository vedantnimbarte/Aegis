"use client";

import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import {
  ShieldHalf,
  Radar,
  ShieldCheck,
  GitBranch,
  Wrench,
  ArrowRight,
  Check,
  X,
  Github,
  Twitter,
  Loader2,
  Box,
  KeyRound,
  Trash2,
  Network,
  GitPullRequest,
  ChevronDown,
  AlertTriangle,
  FileSearch,
  type LucideIcon,
} from "lucide-react";

/* -------------------------------------------------------------------------- */
/*  The signature: a live in-product scan activity feed.                      */
/*  Aegis runs autonomously in the cloud — the hero shows a scan streaming    */
/*  in from the product, ending in a VALIDATED finding.                       */
/* -------------------------------------------------------------------------- */

type Tone = "step" | "alert" | "note" | "result" | "action";

type Activity = { text: string; meta?: string; tone: Tone; delay: number };

const ACTIVITY: Activity[] = [
  { text: "Cloned repository into an isolated sandbox", tone: "step", delay: 0 },
  { text: "Mapped attack surface", meta: "34 routes · 6 auth boundaries", tone: "step", delay: 820 },
  { text: "Probing broken object-level authorization", meta: "GET /api/v1/invoices/:id", tone: "step", delay: 1040 },
  { text: "Executed exploit in isolated sandbox", tone: "step", delay: 980 },
  { text: "Foreign tenant invoice exposed", meta: "HTTP 200", tone: "alert", delay: 1040 },
  { text: "Replayed 3× — confirmed, not a false positive", tone: "note", delay: 860 },
  { text: "Validated", meta: "CWE-639 · CVSS 8.1 · High", tone: "result", delay: 720 },
  { text: "Remediation pull request drafted", tone: "action", delay: 560 },
];

function usePrefersReducedMotion() {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    setReduced(mq.matches);
    const handler = () => setReduced(mq.matches);
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);
  return reduced;
}

function ActivityRow({ item, active }: { item: Activity; active: boolean }) {
  if (item.tone === "result") {
    return (
      <div className="mt-1 flex items-center gap-2.5 rounded-lg border border-signal/25 bg-signal/[0.06] px-3 py-2.5 motion-safe:animate-fade-up">
        <ShieldCheck className="h-4 w-4 shrink-0 text-signal" strokeWidth={2} />
        <span className="text-[13px] font-semibold text-fg">{item.text}</span>
        {item.meta ? (
          <span className="ml-auto font-mono text-[11px] text-signal">{item.meta}</span>
        ) : null}
      </div>
    );
  }

  if (item.tone === "note") {
    return (
      <p className="pl-6 text-[12px] leading-relaxed text-faint motion-safe:animate-fade-up">
        {item.text}
      </p>
    );
  }

  if (item.tone === "action") {
    return (
      <div className="flex items-center gap-2 text-[13px] text-cyan-soft motion-safe:animate-fade-up">
        <GitPullRequest className="h-3.5 w-3.5 shrink-0" strokeWidth={2} />
        {item.text}
      </div>
    );
  }

  if (item.tone === "alert") {
    return (
      <div className="flex items-start gap-2.5 text-[13px] text-danger motion-safe:animate-fade-up">
        <AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0" strokeWidth={2} />
        <span>
          {item.text}
          {item.meta ? <span className="ml-2 font-mono text-[11px] opacity-80">{item.meta}</span> : null}
        </span>
      </div>
    );
  }

  // step
  return (
    <div className="flex items-start gap-2.5 motion-safe:animate-fade-up">
      {active ? (
        <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-cyan motion-safe:animate-pulse-dot" />
      ) : (
        <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-signal" strokeWidth={2.5} />
      )}
      <span className="text-[13px] leading-relaxed">
        <span className={active ? "text-fg" : "text-muted"}>{item.text}</span>
        {item.meta ? <span className="ml-2 font-mono text-[11px] text-faint">{item.meta}</span> : null}
      </span>
    </div>
  );
}

function AttackConsole() {
  const reduced = usePrefersReducedMotion();
  const [visible, setVisible] = useState(0);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  useEffect(() => {
    if (reduced) {
      setVisible(ACTIVITY.length);
      return;
    }
    let elapsed = 300;
    ACTIVITY.forEach((item, i) => {
      elapsed += item.delay;
      const id = setTimeout(() => setVisible(i + 1), elapsed);
      timers.current.push(id);
    });
    const captured = timers.current;
    return () => captured.forEach(clearTimeout);
  }, [reduced]);

  const done = visible >= ACTIVITY.length;

  return (
    <div className="relative">
      {/* ambient glow behind the panel — restrained */}
      <div
        aria-hidden
        className="absolute -inset-6 -z-10 rounded-[2rem] bg-cyan/10 blur-3xl motion-safe:animate-drift"
      />
      <div className="overflow-hidden rounded-xl border border-line bg-[#0B0E15]/95 shadow-2xl backdrop-blur-sm glow-accent">
        {/* product panel header — a scan running inside the app */}
        <div className="flex items-center gap-2.5 border-b border-line bg-surface/70 px-4 py-3">
          <span className="grid h-6 w-6 shrink-0 place-items-center rounded-md border border-line bg-ink text-cyan-soft">
            <Radar className="h-3.5 w-3.5" strokeWidth={2} />
          </span>
          <span className="truncate font-mono text-[12px] text-fg">acme/payments-api</span>
          <span className="hidden shrink-0 rounded border border-line bg-ink px-1.5 py-0.5 font-mono text-[10px] text-muted sm:inline">
            main
          </span>
          <span
            className={`ml-auto flex shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.12em] ${
              done ? "border-signal/30 text-signal" : "border-cyan/30 text-cyan-soft"
            }`}
          >
            <span
              className={`h-1.5 w-1.5 rounded-full ${
                done ? "bg-signal" : "bg-cyan motion-safe:animate-pulse-dot"
              }`}
            />
            {done ? "Validated" : "Scanning"}
          </span>
        </div>

        {/* activity feed */}
        <div className="min-h-[18rem] space-y-2.5 p-5">
          {ACTIVITY.slice(0, visible).map((item, i) => (
            <ActivityRow key={i} item={item} active={!done && i === visible - 1 && item.tone === "step"} />
          ))}
        </div>
      </div>

      {/* caption grounding the panel in the product's real claim */}
      <p className="mt-4 text-center text-[12px] text-faint">
        Every finding is executed and replayed before it reaches your dashboard.
      </p>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  Waitlist form                                                             */
/* -------------------------------------------------------------------------- */

function WaitlistForm() {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<"idle" | "loading" | "done">("idle");
  const [error, setError] = useState<string | null>(null);

  function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (status === "loading") return;
    const valid = /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim());
    if (!valid) {
      setError("Enter a valid work email so we can reach you.");
      return;
    }
    setError(null);
    setStatus("loading");
    // Simulated request — wire to the real API later.
    setTimeout(() => setStatus("done"), 750);
  }

  if (status === "done") {
    return (
      <div
        role="status"
        className="flex items-center gap-3 rounded-lg border border-signal/30 bg-signal/[0.07] px-4 py-3.5 motion-safe:animate-fade-up"
      >
        <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-signal/15 text-signal">
          <Check className="h-4 w-4" strokeWidth={2.5} />
        </span>
        <div>
          <p className="font-display text-sm font-semibold text-fg">You&rsquo;re on the list.</p>
          <p className="text-[13px] text-muted">We&rsquo;ll email early access to your first scan soon.</p>
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} noValidate className="w-full">
      <div className="flex flex-col gap-2.5 sm:flex-row">
        <div className="relative flex-1">
          <label htmlFor="email" className="sr-only">
            Work email
          </label>
          <input
            id="email"
            type="email"
            inputMode="email"
            autoComplete="email"
            placeholder="you@company.com"
            value={email}
            onChange={(e) => {
              setEmail(e.target.value);
              if (error) setError(null);
            }}
            aria-invalid={Boolean(error)}
            aria-describedby={error ? "email-error" : undefined}
            className="w-full rounded-lg border border-line bg-surface/80 px-4 py-3 font-mono text-[13px] text-fg placeholder:text-faint transition-colors focus:border-cyan/60 focus:bg-surface"
          />
        </div>
        <button
          type="submit"
          disabled={status === "loading"}
          className="group inline-flex items-center justify-center gap-2 rounded-lg bg-cyan px-5 py-3 font-display text-[13px] font-semibold text-obsidian shadow-lg shadow-cyan/20 transition-all hover:bg-cyan-soft hover:shadow-cyan/30 disabled:opacity-70"
        >
          {status === "loading" ? (
            <>
              <Loader2 className="h-4 w-4 animate-spin" />
              Joining
            </>
          ) : (
            <>
              Join the waitlist
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" />
            </>
          )}
        </button>
      </div>
      {error ? (
        <p id="email-error" className="mt-2.5 font-mono text-[11px] text-danger">
          {error}
        </p>
      ) : (
        <p className="mt-2.5 font-mono text-[11px] text-faint">
          No spam. Early access, then a founding-user rate.
        </p>
      )}
    </form>
  );
}

/* -------------------------------------------------------------------------- */
/*  Features — framed as the product's real continuous loop                   */
/* -------------------------------------------------------------------------- */

type Feature = {
  step: string;
  phase: string;
  title: string;
  body: string;
  Icon: LucideIcon;
};

const FEATURES: Feature[] = [
  {
    step: "01",
    phase: "Monitor",
    title: "Continuous GitHub monitoring",
    body: "Aegis watches every push and pull request, re-testing the attack surface the moment your code changes.",
    Icon: GitBranch,
  },
  {
    step: "02",
    phase: "Attack",
    title: "Autonomous pentesting",
    body: "Multi-agent AI plans, executes, and pivots like a real attacker across your routes and auth boundaries — no scripts to write.",
    Icon: Radar,
  },
  {
    step: "03",
    phase: "Validate",
    title: "Real exploit validation",
    body: "Every finding ships with a working proof-of-concept, replayed in an isolated sandbox. Zero false positives by construction.",
    Icon: ShieldCheck,
  },
  {
    step: "04",
    phase: "Remediate",
    title: "Auto-remediation patches",
    body: "Get an AI-authored fix and a ready-to-open pull request alongside each validated vulnerability.",
    Icon: Wrench,
  },
];

function FeatureCard({ step, phase, title, body, Icon }: Feature) {
  return (
    <article className="group relative flex flex-col overflow-hidden rounded-xl border border-line bg-surface/40 p-5 transition-all duration-300 hover:-translate-y-0.5 hover:border-cyan/40 hover:bg-surface/70 sm:p-6">
      {/* hover glow */}
      <div
        aria-hidden
        className="pointer-events-none absolute -right-16 -top-16 h-40 w-40 rounded-full bg-cyan/10 opacity-0 blur-2xl transition-opacity duration-300 group-hover:opacity-100"
      />
      <div className="mb-4 flex items-center justify-between">
        <span className="grid h-9 w-9 place-items-center rounded-lg border border-line bg-ink text-cyan-soft transition-colors group-hover:border-cyan/50 group-hover:text-cyan">
          <Icon className="h-4 w-4" strokeWidth={1.75} />
        </span>
        <span className="font-mono text-[10px] uppercase tracking-[0.14em] text-faint">
          {step} · {phase}
        </span>
      </div>
      <h3 className="font-display text-[15px] font-semibold text-fg">{title}</h3>
      <p className="mt-1.5 text-[13px] leading-relaxed text-muted">{body}</p>
    </article>
  );
}

/* -------------------------------------------------------------------------- */
/*  Small shared section heading                                               */
/* -------------------------------------------------------------------------- */

function SectionHeading({
  eyebrow,
  title,
  children,
}: {
  eyebrow: string;
  title: string;
  children?: ReactNode;
}) {
  return (
    <div className="mb-10 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
      <div>
        <p className="mb-2.5 font-mono text-[11px] uppercase tracking-[0.14em] text-cyan-soft">
          {eyebrow}
        </p>
        <h2 className="max-w-md font-display text-2xl font-bold tracking-[-0.01em] text-fg text-balance sm:text-3xl">
          {title}
        </h2>
      </div>
      {children ? (
        <p className="max-w-sm text-[13px] leading-relaxed text-muted">{children}</p>
      ) : null}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  Sample finding — proof of what you actually receive                        */
/* -------------------------------------------------------------------------- */

function SampleFinding() {
  return (
    <div className="overflow-hidden rounded-xl border border-line bg-surface/40">
      {/* card header */}
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2 border-b border-line px-5 py-4">
        <span className="inline-flex items-center gap-1.5 rounded-md border border-amber/30 bg-amber/10 px-2 py-1 font-mono text-[11px] font-medium uppercase tracking-wider text-amber">
          <span className="h-1.5 w-1.5 rounded-full bg-amber" />
          High
        </span>
        <h3 className="font-display text-sm font-semibold text-fg">
          Broken object-level authorization (IDOR)
        </h3>
        <span className="ml-auto inline-flex items-center gap-1.5 rounded-full border border-signal/30 px-2.5 py-1 font-mono text-[11px] text-signal">
          <Check className="h-3.5 w-3.5" strokeWidth={2.5} />
          Validated
        </span>
      </div>

      {/* meta row */}
      <dl className="flex flex-wrap gap-x-6 gap-y-2 border-b border-line px-5 py-3 font-mono text-[11px]">
        {[
          { k: "Endpoint", v: "GET /api/v1/invoices/:id" },
          { k: "Weakness", v: "CWE-639" },
          { k: "Severity", v: "CVSS 8.1" },
          { k: "Branch", v: "main" },
          { k: "Confidence", v: "Replayed 3×" },
        ].map((m) => (
          <div key={m.k} className="flex items-center gap-1.5">
            <dt className="text-faint">{m.k}</dt>
            <dd className="text-muted">{m.v}</dd>
          </div>
        ))}
      </dl>

      <div className="px-5 py-4">
        <p className="text-[13px] leading-relaxed text-muted">
          A request authenticated as one tenant could read another tenant&rsquo;s invoice by changing
          the record ID. Aegis confirmed the exposure by retrieving live data across the boundary.
        </p>

        {/* expandable captured evidence */}
        <details className="group mt-4 overflow-hidden rounded-lg border border-line bg-[#0B0E15]">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-4 py-3 text-[13px] font-medium text-fg transition-colors hover:text-cyan-soft [&::-webkit-details-marker]:hidden">
            <span className="inline-flex items-center gap-2">
              <FileSearch className="h-4 w-4 text-cyan-soft" strokeWidth={1.75} />
              View captured evidence
            </span>
            <ChevronDown
              className="h-4 w-4 shrink-0 text-faint transition-transform duration-200 group-open:rotate-180"
              strokeWidth={2}
            />
          </summary>
          <div className="space-y-3 border-t border-line px-4 py-4">
            <div>
              <p className="mb-1.5 font-mono text-[10px] uppercase tracking-[0.14em] text-faint">Request</p>
              <div className="overflow-x-auto rounded-md bg-obsidian px-3 py-2.5 font-mono text-[12px] leading-relaxed text-muted">
                <span className="text-cyan-soft">GET</span> /api/v1/invoices/1042
                <br />
                Authorization: Bearer &lt;tenant-A&gt;
              </div>
            </div>
            <div>
              <p className="mb-1.5 font-mono text-[10px] uppercase tracking-[0.14em] text-faint">Response</p>
              <div className="overflow-x-auto rounded-md bg-obsidian px-3 py-2.5 font-mono text-[12px] leading-relaxed text-muted">
                <span className="text-signal">200 OK</span>
                <br />
                {"{ "}
                <span className="text-danger">&quot;tenant&quot;: &quot;tenant-B&quot;</span>
                , &quot;total&quot;: &quot;$48,210.00&quot; {"}"}
              </div>
              <p className="mt-2 font-mono text-[11px] text-danger">
                Tenant-A credentials read tenant-B&rsquo;s invoice.
              </p>
            </div>
          </div>
        </details>

        {/* suggested fix */}
        <div className="mt-4 overflow-hidden rounded-lg border border-line bg-[#0B0E15]">
          <p className="border-b border-line px-4 py-2.5 font-mono text-[10px] uppercase tracking-[0.14em] text-faint">
            Suggested fix
          </p>
          <pre className="overflow-x-auto px-4 py-3 font-mono text-[12px] leading-relaxed text-muted">
            <code>
              {"  invoice = Invoice.find(params[:id])\n"}
              <span className="text-signal">{"+ authorize!(:read, invoice)\n"}</span>
              {"  render json: invoice"}
            </code>
          </pre>
        </div>

        <a
          href="#"
          className="mt-4 inline-flex items-center gap-1.5 text-[12px] font-medium text-cyan-soft transition-colors hover:text-cyan"
        >
          <GitPullRequest className="h-3.5 w-3.5" strokeWidth={2} />
          Open the remediation pull request
        </a>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  Comparison — the wedge: proof, not noise                                   */
/* -------------------------------------------------------------------------- */

const COMPARE: { label: string; legacy: string; aegis: string }[] = [
  { label: "False positives", legacy: "A triage queue full of maybes", aegis: "Zero — every finding is exploited" },
  { label: "Evidence", legacy: "A severity guess on a code pattern", aegis: "A working PoC, replayed in a sandbox" },
  { label: "The fix", legacy: "You research and write it", aegis: "AI patch, opened as a pull request" },
  { label: "Coverage", legacy: "A point-in-time scan", aegis: "Continuous, on every commit" },
];

function Comparison() {
  return (
    <div className="overflow-hidden rounded-xl border border-line">
      <div className="grid grid-cols-[1fr_1fr] bg-surface/60 font-mono text-[10px] uppercase tracking-[0.14em] sm:grid-cols-[minmax(0,10rem)_1fr_1fr]">
        <div className="hidden px-5 py-3.5 text-faint sm:block" />
        <div className="border-l border-line px-5 py-3.5 text-faint">Legacy SAST / DAST</div>
        <div className="border-l border-line bg-cyan/[0.06] px-5 py-3.5 text-cyan-soft">Aegis</div>
      </div>
      {COMPARE.map((row) => (
        <div
          key={row.label}
          className="grid grid-cols-[1fr_1fr] border-t border-line sm:grid-cols-[minmax(0,10rem)_1fr_1fr]"
        >
          <div className="hidden px-5 py-4 font-mono text-[11px] uppercase tracking-wider text-faint sm:block">
            {row.label}
          </div>
          <div className="flex items-start gap-2 border-l border-line px-5 py-4 text-[13px] text-muted">
            <X className="mt-0.5 h-3.5 w-3.5 shrink-0 text-faint" strokeWidth={2.5} />
            {row.legacy}
          </div>
          <div className="flex items-start gap-2 border-l border-line bg-cyan/[0.04] px-5 py-4 text-[13px] text-fg">
            <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-cyan" strokeWidth={2.5} />
            {row.aegis}
          </div>
        </div>
      ))}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  Safe by design — the objection every security buyer has                    */
/* -------------------------------------------------------------------------- */

const SAFETY: { Icon: LucideIcon; title: string; body: string }[] = [
  {
    Icon: Box,
    title: "Ephemeral sandboxes",
    body: "Each scan spins up an isolated container that is destroyed the moment it finishes.",
  },
  {
    Icon: KeyRound,
    title: "Least-privilege access",
    body: "A scoped GitHub App reads your code and opens PRs — nothing more. No production access, ever.",
  },
  {
    Icon: Network,
    title: "Exploits stay contained",
    body: "Every attack runs against the sandboxed clone, never against your live systems or users.",
  },
  {
    Icon: Trash2,
    title: "No data retention",
    body: "Your source and scan artifacts are purged after each run. We keep the findings, not your code.",
  },
];

function SafeByDesign() {
  return (
    <div className="grid gap-3.5 sm:grid-cols-2">
      {SAFETY.map(({ Icon, title, body }) => (
        <article key={title} className="flex gap-4 rounded-xl border border-line bg-surface/40 p-5">
          <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-line bg-ink text-cyan-soft">
            <Icon className="h-4 w-4" strokeWidth={1.75} />
          </span>
          <div>
            <h3 className="font-display text-[15px] font-semibold text-fg">{title}</h3>
            <p className="mt-1 text-[13px] leading-relaxed text-muted">{body}</p>
          </div>
        </article>
      ))}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  FAQ — native <details>, no JS                                              */
/* -------------------------------------------------------------------------- */

const FAQ: { q: string; a: string }[] = [
  {
    q: "What languages and frameworks do you support?",
    a: "Aegis reasons about running behavior, not a fixed rule set, so it works across most web stacks — JavaScript/TypeScript, Python, Ruby, Go, and Java to start. Tell us your stack when you join and we'll confirm coverage.",
  },
  {
    q: "Does Aegis need access to production?",
    a: "No. Aegis clones your repository into an isolated sandbox and attacks that copy. It never touches your live systems, data, or users.",
  },
  {
    q: "GitHub only, or GitLab too?",
    a: "The beta connects to GitHub. GitLab and Bitbucket are on the roadmap — let us know what you use and we'll prioritize accordingly.",
  },
  {
    q: "Will it open pull requests automatically?",
    a: "Aegis proposes a fix as a pull request for every validated finding. You review and merge — nothing lands in your codebase without your approval.",
  },
  {
    q: "What will it cost after the beta?",
    a: "Beta is free. Early users lock in a founding rate when we launch paid plans. Pricing scales with the number of repositories under continuous testing.",
  },
];

function FaqList() {
  return (
    <div className="divide-y divide-line overflow-hidden rounded-xl border border-line bg-surface/40">
      {FAQ.map(({ q, a }) => (
        <details key={q} className="group">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-4 px-5 py-4 font-display text-sm font-medium text-fg transition-colors hover:text-cyan-soft [&::-webkit-details-marker]:hidden">
            {q}
            <ChevronDown
              className="h-4 w-4 shrink-0 text-faint transition-transform duration-200 group-open:rotate-180"
              strokeWidth={2}
            />
          </summary>
          <p className="px-5 pb-4 text-[13px] leading-relaxed text-muted">{a}</p>
        </details>
      ))}
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/*  Page                                                                       */
/* -------------------------------------------------------------------------- */

export default function Home() {
  return (
    <main className="relative min-h-screen overflow-hidden bg-obsidian">
      {/* backdrop layers */}
      <div aria-hidden className="pointer-events-none absolute inset-0 bg-grid" />
      <div
        aria-hidden
        className="pointer-events-none absolute left-1/2 top-[-12%] -z-0 h-[36rem] w-[54rem] -translate-x-1/2 rounded-full bg-cyan/[0.07] blur-[130px]"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-cyan/30 to-transparent"
      />

      <div className="relative z-10 mx-auto flex max-w-6xl flex-col px-5 sm:px-8">
        {/* Nav */}
        <header className="flex items-center justify-between py-5">
          <a href="#" className="flex items-center gap-2.5">
            <span className="grid h-8 w-8 place-items-center rounded-lg border border-cyan/40 bg-cyan/10 text-cyan-soft">
              <ShieldHalf className="h-4 w-4" strokeWidth={2} />
            </span>
            <span className="font-display text-[15px] font-semibold tracking-tight text-fg">Aegis</span>
          </a>
          <span className="hidden items-center gap-2 rounded-full border border-line bg-surface/60 px-3 py-1.5 font-mono text-[11px] text-muted sm:flex">
            <span className="h-1.5 w-1.5 rounded-full bg-signal motion-safe:animate-pulse-dot" />
            Private beta · onboarding soon
          </span>
        </header>

        {/* Hero */}
        <section className="grid items-center gap-12 py-10 lg:grid-cols-[1.05fr_1fr] lg:gap-10 lg:py-16">
          <div>
            <p className="mb-5 inline-flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.14em] text-cyan-soft">
              <span className="h-px w-7 bg-cyan/60" />
              autonomous offensive security
            </p>
            <h1 className="font-display text-[2rem] font-bold leading-[1.08] tracking-[-0.02em] text-fg text-balance sm:text-[2.5rem] lg:text-5xl">
              Continuous AI
              <br />
              <span className="text-cyan-soft">penetration testing</span>
            </h1>
            <p className="mt-5 max-w-lg text-[13px] leading-relaxed text-muted sm:text-sm">
              Aegis dynamically executes code in isolated sandboxes to detect, exploit, and validate
              real security vulnerabilities — delivering zero-false-positive reports.
            </p>

            <div className="mt-8 max-w-lg">
              <WaitlistForm />
            </div>

            <dl className="mt-9 flex flex-wrap gap-x-9 gap-y-4 border-t border-line pt-6">
              {[
                { k: "0", v: "false positives" },
                { k: "24/7", v: "continuous coverage" },
                { k: "PoC", v: "on every finding" },
              ].map((s) => (
                <div key={s.v}>
                  <dt className="font-display text-xl font-semibold text-fg">{s.k}</dt>
                  <dd className="mt-0.5 font-mono text-[10px] uppercase tracking-[0.12em] text-faint">{s.v}</dd>
                </div>
              ))}
            </dl>
          </div>

          <AttackConsole />
        </section>

        {/* Features — the continuous loop */}
        <section className="py-14 lg:py-20">
          <div className="mb-10 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="mb-2.5 font-mono text-[11px] uppercase tracking-[0.14em] text-cyan-soft">
                the loop
              </p>
              <h2 className="max-w-md font-display text-2xl font-bold tracking-[-0.01em] text-fg text-balance sm:text-3xl">
                One closed loop, running while you ship
              </h2>
            </div>
            <p className="max-w-sm text-[13px] leading-relaxed text-muted">
              Monitor, attack, validate, remediate — Aegis keeps the cycle turning on every commit so
              nothing regresses between releases.
            </p>
          </div>

          <div className="grid gap-3.5 sm:grid-cols-2">
            {FEATURES.map((f) => (
              <FeatureCard key={f.step} {...f} />
            ))}
          </div>
        </section>

        {/* Sample finding — proof of the deliverable */}
        <section className="py-14 lg:py-20">
          <SectionHeading eyebrow="what you get" title="A validated exploit, not a warning">
            Every finding arrives with the request that broke in, the data it exposed, and the patch
            that closes it.
          </SectionHeading>
          <SampleFinding />
        </section>

        {/* Comparison — the wedge */}
        <section className="py-14 lg:py-20">
          <SectionHeading eyebrow="why aegis" title="Proof, not a queue of maybes">
            Traditional scanners hand you noise to triage. Aegis only reports what it could actually
            exploit.
          </SectionHeading>
          <Comparison />
        </section>

        {/* Safe by design — objection handling */}
        <section className="py-14 lg:py-20">
          <SectionHeading eyebrow="safe by design" title="It attacks a copy, never your systems">
            Aegis is built to run offensive tooling without ever putting your production or data at
            risk.
          </SectionHeading>
          <SafeByDesign />
        </section>

        {/* FAQ */}
        <section className="py-14 lg:py-20">
          <SectionHeading eyebrow="questions" title="Answers before you ask" />
          <FaqList />
        </section>

        {/* Closing CTA */}
        <section className="py-14 lg:py-20">
          <div className="relative overflow-hidden rounded-2xl border border-cyan/25 bg-surface/40 px-6 py-12 text-center sm:px-12 sm:py-16">
            <div
              aria-hidden
              className="pointer-events-none absolute left-1/2 top-0 -z-0 h-56 w-[36rem] max-w-full -translate-x-1/2 rounded-full bg-cyan/10 blur-[100px]"
            />
            <div className="relative mx-auto max-w-xl">
              <h2 className="font-display text-2xl font-bold tracking-[-0.01em] text-fg text-balance sm:text-3xl">
                Start protecting your repos
              </h2>
              <p className="mx-auto mt-3 max-w-md text-[13px] leading-relaxed text-muted sm:text-sm">
                Join the private beta and put your first repository through a full autonomous pentest.
              </p>
              <div className="mx-auto mt-7 max-w-md text-left">
                <WaitlistForm />
              </div>
            </div>
          </div>
        </section>

        {/* Footer */}
        <footer className="mt-6 flex flex-col items-center justify-between gap-5 border-t border-line py-7 sm:flex-row">
          <div className="flex items-center gap-2.5">
            <span className="grid h-6 w-6 place-items-center rounded-md border border-cyan/30 bg-cyan/10 text-cyan-soft">
              <ShieldHalf className="h-3.5 w-3.5" strokeWidth={2} />
            </span>
            <p className="font-mono text-[11px] text-faint">
              © {new Date().getFullYear()} Aegis Security. All rights reserved.
            </p>
          </div>
          <nav className="flex items-center gap-2">
            <a
              href="https://x.com"
              target="_blank"
              rel="noopener noreferrer"
              aria-label="Aegis on X"
              className="grid h-8 w-8 place-items-center rounded-lg border border-line text-muted transition-colors hover:border-cyan/40 hover:text-fg"
            >
              <Twitter className="h-4 w-4" />
            </a>
            <a
              href="https://github.com"
              target="_blank"
              rel="noopener noreferrer"
              aria-label="Aegis on GitHub"
              className="grid h-8 w-8 place-items-center rounded-lg border border-line text-muted transition-colors hover:border-cyan/40 hover:text-fg"
            >
              <Github className="h-4 w-4" />
            </a>
          </nav>
        </footer>
      </div>
    </main>
  );
}
