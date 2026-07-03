"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  ShieldHalf,
  Radar,
  ShieldCheck,
  GitBranch,
  Wrench,
  ArrowRight,
  Check,
  Github,
  Twitter,
  Loader2,
  type LucideIcon,
} from "lucide-react";

/* -------------------------------------------------------------------------- */
/*  The signature: a scripted autonomous-pentest session.                     */
/*  Aegis proves exploits instead of just flagging them, so the hero shows    */
/*  the console doing exactly that — ending in a VALIDATED verdict.           */
/* -------------------------------------------------------------------------- */

type Tone = "cmd" | "muted" | "agent" | "exploit" | "danger" | "ok";

type Line = { text: string; tone: Tone; delay: number };

const SESSION: Line[] = [
  { text: "$ aegis scan --target acme/payments-api --mode deep", tone: "cmd", delay: 0 },
  { text: "cloning repository into isolated sandbox … ok", tone: "muted", delay: 620 },
  { text: "mapping attack surface … 34 routes · 6 auth boundaries", tone: "agent", delay: 900 },
  { text: "hypothesis: IDOR on GET /api/v1/invoices/:id", tone: "agent", delay: 1080 },
  { text: "crafting exploit … executing in sandbox", tone: "agent", delay: 980 },
  { text: "GET /api/v1/invoices/1042 → 200  (foreign tenant data)", tone: "exploit", delay: 1040 },
  { text: "replayed 3× · confirmed · not a false positive", tone: "muted", delay: 900 },
  { text: "✔ VALIDATED   CWE-639   CVSS 8.1 High", tone: "ok", delay: 720 },
  { text: "PoC captured · remediation patch generated", tone: "danger", delay: 560 },
];

const TONE_CLASS: Record<Tone, string> = {
  cmd: "text-fg",
  muted: "text-faint",
  agent: "text-violet-soft",
  exploit: "text-cyan",
  danger: "text-amber",
  ok: "text-signal",
};

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

function AttackConsole() {
  const reduced = usePrefersReducedMotion();
  const [visible, setVisible] = useState(0);
  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);

  useEffect(() => {
    if (reduced) {
      setVisible(SESSION.length);
      return;
    }
    let elapsed = 300;
    SESSION.forEach((line, i) => {
      elapsed += line.delay;
      const id = setTimeout(() => setVisible(i + 1), elapsed);
      timers.current.push(id);
    });
    const captured = timers.current;
    return () => captured.forEach(clearTimeout);
  }, [reduced]);

  const done = visible >= SESSION.length;

  return (
    <div className="relative">
      {/* ambient glow behind the console */}
      <div
        aria-hidden
        className="absolute -inset-8 -z-10 rounded-[2rem] bg-violet/20 blur-3xl motion-safe:animate-drift"
      />
      <div className="overflow-hidden rounded-xl border border-line bg-[#090C13]/95 shadow-2xl backdrop-blur-sm glow-violet">
        {/* titlebar */}
        <div className="flex items-center gap-2 border-b border-line bg-surface/70 px-4 py-3">
          <span className="h-3 w-3 rounded-full bg-danger/70" />
          <span className="h-3 w-3 rounded-full bg-amber/70" />
          <span className="h-3 w-3 rounded-full bg-signal/70" />
          <span className="ml-3 font-mono text-xs tracking-tight text-muted">
            aegis-agent · run #4471
          </span>
          <span className="ml-auto flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-widest text-signal">
            <span className="h-1.5 w-1.5 rounded-full bg-signal motion-safe:animate-pulse-dot" />
            {done ? "validated" : "live"}
          </span>
        </div>

        {/* stream */}
        <div className="min-h-[19rem] space-y-1.5 p-5 font-mono text-[13px] leading-relaxed sm:text-sm">
          {SESSION.slice(0, visible).map((line, i) => {
            const isLast = i === visible - 1;
            const showCursor = !done && isLast;
            const prefix =
              line.tone === "cmd"
                ? ""
                : line.tone === "agent"
                ? "[agent] "
                : line.tone === "exploit"
                ? "[exploit] "
                : line.tone === "ok"
                ? ""
                : line.tone === "danger"
                ? "  ↳ "
                : "  ";
            return (
              <div
                key={i}
                className={`motion-safe:animate-fade-up ${TONE_CLASS[line.tone]} ${
                  line.tone === "ok"
                    ? "mt-2 rounded-md border border-signal/25 bg-signal/[0.06] px-2.5 py-1.5 font-semibold"
                    : ""
                }`}
              >
                {line.tone !== "cmd" && line.tone !== "ok" && (
                  <span className="select-none text-faint">{prefix}</span>
                )}
                {line.tone === "cmd" && <span className="select-none text-signal">➜ </span>}
                <span>{line.text.replace(/^\$ /, "")}</span>
                {showCursor && (
                  <span className="ml-0.5 inline-block h-4 w-2 translate-y-0.5 bg-violet-soft align-middle motion-safe:animate-blink" />
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* caption grounding the demo in the product's real claim */}
      <p className="mt-4 text-center font-mono text-xs text-faint">
        Every finding is executed and replayed before it reaches you.
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
        className="flex items-center gap-3 rounded-lg border border-signal/30 bg-signal/[0.07] px-4 py-4 motion-safe:animate-fade-up"
      >
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-signal/15 text-signal">
          <Check className="h-5 w-5" strokeWidth={2.5} />
        </span>
        <div>
          <p className="font-display text-sm font-semibold text-fg">Thanks for joining — you&rsquo;re on the list.</p>
          <p className="text-sm text-muted">We&rsquo;ll email early access to your first scan soon.</p>
        </div>
      </div>
    );
  }

  return (
    <form onSubmit={onSubmit} noValidate className="w-full">
      <div className="flex flex-col gap-3 sm:flex-row">
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
            className="w-full rounded-lg border border-line bg-surface/80 px-4 py-3.5 font-mono text-sm text-fg placeholder:text-faint transition-colors focus:border-violet/60 focus:bg-surface"
          />
        </div>
        <button
          type="submit"
          disabled={status === "loading"}
          className="group inline-flex items-center justify-center gap-2 rounded-lg bg-violet px-6 py-3.5 font-display text-sm font-semibold text-white shadow-lg shadow-violet/25 transition-all hover:bg-violet-soft hover:shadow-violet/40 focus-visible:outline-violet-soft disabled:opacity-70"
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
        <p id="email-error" className="mt-2.5 font-mono text-xs text-danger">
          {error}
        </p>
      ) : (
        <p className="mt-2.5 font-mono text-xs text-faint">
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
    <article className="group relative flex flex-col overflow-hidden rounded-xl border border-line bg-surface/40 p-6 transition-all duration-300 hover:-translate-y-1 hover:border-violet/40 hover:bg-surface/70 sm:p-7">
      {/* hover glow */}
      <div
        aria-hidden
        className="pointer-events-none absolute -right-16 -top-16 h-40 w-40 rounded-full bg-violet/10 opacity-0 blur-2xl transition-opacity duration-300 group-hover:opacity-100"
      />
      <div className="mb-5 flex items-center justify-between">
        <span className="grid h-11 w-11 place-items-center rounded-lg border border-line bg-ink text-violet-soft transition-colors group-hover:border-violet/50 group-hover:text-violet">
          <Icon className="h-5 w-5" strokeWidth={1.75} />
        </span>
        <span className="font-mono text-[11px] uppercase tracking-[0.2em] text-faint">
          {step} · {phase}
        </span>
      </div>
      <h3 className="font-display text-lg font-semibold text-fg">{title}</h3>
      <p className="mt-2 text-sm leading-relaxed text-muted">{body}</p>
    </article>
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
        className="pointer-events-none absolute left-1/2 top-[-10%] -z-0 h-[40rem] w-[60rem] -translate-x-1/2 rounded-full bg-violet/10 blur-[120px]"
      />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-violet/40 to-transparent"
      />

      <div className="relative z-10 mx-auto flex max-w-6xl flex-col px-5 sm:px-8">
        {/* Nav */}
        <header className="flex items-center justify-between py-6">
          <a href="#" className="flex items-center gap-2.5">
            <span className="grid h-9 w-9 place-items-center rounded-lg border border-violet/40 bg-violet/10 text-violet-soft">
              <ShieldHalf className="h-5 w-5" strokeWidth={2} />
            </span>
            <span className="font-display text-lg font-semibold tracking-tight text-fg">Aegis</span>
          </a>
          <span className="hidden items-center gap-2 rounded-full border border-line bg-surface/60 px-3.5 py-1.5 font-mono text-xs text-muted sm:flex">
            <span className="h-1.5 w-1.5 rounded-full bg-signal motion-safe:animate-pulse-dot" />
            Private beta · onboarding soon
          </span>
        </header>

        {/* Hero */}
        <section className="grid items-center gap-14 py-12 lg:grid-cols-[1.05fr_1fr] lg:gap-10 lg:py-20">
          <div>
            <p className="mb-6 inline-flex items-center gap-2 font-mono text-xs uppercase tracking-[0.22em] text-violet-soft">
              <span className="h-px w-8 bg-violet/60" />
              autonomous offensive security
            </p>
            <h1 className="font-display text-4xl font-bold leading-[1.05] tracking-tight text-fg text-balance sm:text-5xl lg:text-6xl">
              Continuous AI
              <br />
              <span className="bg-gradient-to-r from-violet-soft via-violet to-cyan bg-clip-text text-transparent">
                penetration testing
              </span>
            </h1>
            <p className="mt-6 max-w-xl text-base leading-relaxed text-muted sm:text-lg">
              Aegis dynamically executes code in isolated sandboxes to detect, exploit, and validate
              real security vulnerabilities—providing zero-false-positive reports.
            </p>

            <div className="mt-9 max-w-xl">
              <WaitlistForm />
            </div>

            <dl className="mt-10 flex flex-wrap gap-x-10 gap-y-4 border-t border-line pt-6">
              {[
                { k: "0", v: "false positives" },
                { k: "24/7", v: "continuous coverage" },
                { k: "PoC", v: "on every finding" },
              ].map((s) => (
                <div key={s.v}>
                  <dt className="font-display text-2xl font-semibold text-fg">{s.k}</dt>
                  <dd className="font-mono text-xs uppercase tracking-wider text-faint">{s.v}</dd>
                </div>
              ))}
            </dl>
          </div>

          <AttackConsole />
        </section>

        {/* Features — the continuous loop */}
        <section className="py-16 lg:py-24">
          <div className="mb-12 flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="mb-3 font-mono text-xs uppercase tracking-[0.22em] text-violet-soft">
                the loop
              </p>
              <h2 className="max-w-lg font-display text-3xl font-bold tracking-tight text-fg text-balance sm:text-4xl">
                One closed loop, running while you ship
              </h2>
            </div>
            <p className="max-w-sm text-sm leading-relaxed text-muted">
              Monitor, attack, validate, remediate — Aegis keeps the cycle turning on every commit so
              nothing regresses between releases.
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            {FEATURES.map((f) => (
              <FeatureCard key={f.step} {...f} />
            ))}
          </div>
        </section>

        {/* Footer */}
        <footer className="mt-8 flex flex-col items-center justify-between gap-6 border-t border-line py-8 sm:flex-row">
          <div className="flex items-center gap-2.5">
            <span className="grid h-7 w-7 place-items-center rounded-md border border-violet/30 bg-violet/10 text-violet-soft">
              <ShieldHalf className="h-4 w-4" strokeWidth={2} />
            </span>
            <p className="font-mono text-xs text-faint">
              © {new Date().getFullYear()} Aegis Security. All rights reserved.
            </p>
          </div>
          <nav className="flex items-center gap-2">
            <a
              href="https://x.com"
              target="_blank"
              rel="noopener noreferrer"
              aria-label="Aegis on X"
              className="grid h-9 w-9 place-items-center rounded-lg border border-line text-muted transition-colors hover:border-violet/40 hover:text-fg"
            >
              <Twitter className="h-4 w-4" />
            </a>
            <a
              href="https://github.com"
              target="_blank"
              rel="noopener noreferrer"
              aria-label="Aegis on GitHub"
              className="grid h-9 w-9 place-items-center rounded-lg border border-line text-muted transition-colors hover:border-violet/40 hover:text-fg"
            >
              <Github className="h-4 w-4" />
            </a>
          </nav>
        </footer>
      </div>
    </main>
  );
}
