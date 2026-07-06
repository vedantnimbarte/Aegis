"use client";

import { useMutation } from "@tanstack/react-query";
import { Github, Loader2, Lock, Mail, ShieldHalf } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";

import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { buildGitHubAuthUrl } from "@/lib/format";
import { Button, cn } from "@/components/ui";

type Mode = "signin" | "signup";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function LoginPage() {
  const router = useRouter();
  const { isAuthenticated, login } = useAuth();
  const [mounted, setMounted] = useState(false);

  const [mode, setMode] = useState<Mode>("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => setMounted(true), []);
  useEffect(() => {
    if (mounted && isAuthenticated) router.replace("/");
  }, [mounted, isAuthenticated, router]);

  const clientId = process.env.NEXT_PUBLIC_GITHUB_CLIENT_ID;

  const auth = useMutation({
    mutationFn: () =>
      mode === "signin"
        ? api.login(email.trim(), password)
        : api.register(email.trim(), password),
    onSuccess: (token) => {
      login(token);
      router.replace("/");
    },
  });

  function switchMode(next: Mode) {
    setMode(next);
    setFormError(null);
    auth.reset();
  }

  function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setFormError(null);
    const em = email.trim();
    if (!EMAIL_RE.test(em)) {
      setFormError("Enter a valid email address.");
      return;
    }
    if (!password) {
      setFormError("Enter your password.");
      return;
    }
    if (mode === "signup" && password.length < 8) {
      setFormError("Password must be at least 8 characters.");
      return;
    }
    auth.mutate();
  }

  const errorMessage =
    formError ||
    (auth.error instanceof ApiError
      ? auth.error.message
      : auth.error
        ? "Something went wrong. Please try again."
        : null);

  function signInWithGitHub() {
    window.location.href = buildGitHubAuthUrl();
  }

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-obsidian px-5 py-10">
      <div aria-hidden className="pointer-events-none absolute inset-0 bg-grid" />
      <div
        aria-hidden
        className="pointer-events-none absolute left-1/2 top-[-10%] h-[32rem] w-[48rem] -translate-x-1/2 rounded-full bg-cyan/[0.07] blur-[130px]"
      />

      <div className="relative z-10 w-full max-w-sm">
        <div className="mb-8 flex flex-col items-center text-center">
          <span className="mb-5 grid h-12 w-12 place-items-center rounded-xl border border-cyan/40 bg-cyan/10 text-cyan-soft">
            <ShieldHalf className="h-6 w-6" strokeWidth={2} />
          </span>
          <h1 className="font-display text-2xl font-bold tracking-tight text-fg">
            {mode === "signin" ? "Sign in to Aegis" : "Create your account"}
          </h1>
          <p className="mt-2 text-[13px] leading-relaxed text-muted">
            Continuous AI penetration testing for your repositories.
          </p>
        </div>

        <div className="rounded-2xl border border-line bg-surface/50 p-6">
          {/* Mode toggle */}
          <div className="mb-5 grid grid-cols-2 gap-1 rounded-lg border border-line bg-ink p-1">
            {(["signin", "signup"] as Mode[]).map((m) => (
              <button
                key={m}
                type="button"
                onClick={() => switchMode(m)}
                className={cn(
                  "rounded-md py-2 font-display text-[13px] font-semibold transition-colors",
                  mode === m ? "bg-surface text-fg" : "text-muted hover:text-fg"
                )}
              >
                {m === "signin" ? "Sign in" : "Create account"}
              </button>
            ))}
          </div>

          <form onSubmit={onSubmit} noValidate className="space-y-3">
            <Field
              icon={Mail}
              type="email"
              placeholder="you@company.com"
              autoComplete="email"
              value={email}
              onChange={setEmail}
            />
            <Field
              icon={Lock}
              type="password"
              placeholder="Password"
              autoComplete={mode === "signin" ? "current-password" : "new-password"}
              value={password}
              onChange={setPassword}
            />

            {errorMessage ? (
              <p className="rounded-lg border border-danger/30 bg-danger/[0.06] px-3 py-2.5 text-[12px] text-danger">
                {errorMessage}
              </p>
            ) : null}

            <Button type="submit" className="w-full" loading={auth.isPending}>
              {mode === "signin" ? "Sign in" : "Create account"}
            </Button>
          </form>

          {/* Divider */}
          <div className="my-5 flex items-center gap-3">
            <span className="h-px flex-1 bg-line" />
            <span className="font-mono text-[10px] uppercase tracking-wide text-faint">or</span>
            <span className="h-px flex-1 bg-line" />
          </div>

          <Button
            variant="secondary"
            icon={Github}
            className="w-full"
            onClick={signInWithGitHub}
            disabled={!clientId}
          >
            Continue with GitHub
          </Button>
          {!clientId ? (
            <p className="mt-3 text-center font-mono text-[10px] leading-relaxed text-faint">
              Set NEXT_PUBLIC_GITHUB_CLIENT_ID to enable GitHub sign-in.
            </p>
          ) : null}
        </div>
      </div>
    </main>
  );
}

function Field({
  icon: Icon,
  type,
  placeholder,
  autoComplete,
  value,
  onChange,
}: {
  icon: typeof Mail;
  type: string;
  placeholder: string;
  autoComplete: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="relative">
      <Icon
        className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-faint"
        strokeWidth={2}
      />
      <input
        type={type}
        placeholder={placeholder}
        autoComplete={autoComplete}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border border-line bg-ink py-2.5 pl-9 pr-3 text-[13px] text-fg placeholder:text-faint transition-colors focus:border-cyan/60"
      />
    </div>
  );
}
