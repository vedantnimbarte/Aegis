"use client";

import { useMutation } from "@tanstack/react-query";
import { Lock, ShieldHalf } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState, type FormEvent } from "react";

import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button, Spinner } from "@/components/ui";

function ResetInner() {
  const router = useRouter();
  const params = useSearchParams();
  const { login } = useAuth();
  const token = params.get("token") ?? "";

  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const reset = useMutation({
    mutationFn: () => api.resetPassword(token, password),
    onSuccess: (tokens) => {
      login(tokens);
      router.replace("/");
    },
  });

  function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setFormError(null);
    if (password.length < 8) {
      setFormError("Password must be at least 8 characters.");
      return;
    }
    if (password !== confirm) {
      setFormError("Passwords do not match.");
      return;
    }
    reset.mutate();
  }

  const errorMessage =
    formError ||
    (reset.error instanceof ApiError
      ? reset.error.message
      : reset.error
        ? "Something went wrong. Please try again."
        : null);

  return (
    <div className="relative z-10 w-full max-w-sm">
      <div className="mb-8 flex flex-col items-center text-center">
        <span className="mb-5 grid h-12 w-12 place-items-center rounded-xl border border-cyan/40 bg-cyan/10 text-cyan-soft">
          <ShieldHalf className="h-6 w-6" strokeWidth={2} />
        </span>
        <h1 className="font-display text-2xl font-bold tracking-tight text-fg">
          Choose a new password
        </h1>
      </div>

      <div className="rounded-2xl border border-line bg-surface/50 p-6">
        {!token ? (
          <div className="text-center">
            <p className="text-[13px] leading-relaxed text-muted">
              This reset link is missing its token. Request a new one to continue.
            </p>
            <Link
              href="/forgot-password"
              className="mt-5 inline-flex items-center justify-center rounded-lg bg-cyan px-4 py-2.5 font-display text-[13px] font-semibold text-obsidian hover:bg-cyan-soft"
            >
              Request a new link
            </Link>
          </div>
        ) : (
          <form onSubmit={onSubmit} noValidate className="space-y-3">
            <PasswordField
              placeholder="New password"
              autoComplete="new-password"
              value={password}
              onChange={setPassword}
            />
            <PasswordField
              placeholder="Confirm new password"
              autoComplete="new-password"
              value={confirm}
              onChange={setConfirm}
            />

            {errorMessage ? (
              <p className="rounded-lg border border-danger/30 bg-danger/[0.06] px-3 py-2.5 text-[12px] text-danger">
                {errorMessage}
              </p>
            ) : null}

            <Button type="submit" className="w-full" loading={reset.isPending}>
              Update password
            </Button>

            {reset.error instanceof ApiError && reset.error.status === 400 ? (
              <Link
                href="/forgot-password"
                className="block text-center text-[12px] font-medium text-cyan-soft hover:text-cyan"
              >
                Request a new reset link
              </Link>
            ) : null}
          </form>
        )}
      </div>
    </div>
  );
}

function PasswordField({
  placeholder,
  autoComplete,
  value,
  onChange,
}: {
  placeholder: string;
  autoComplete: string;
  value: string;
  onChange: (v: string) => void;
}) {
  return (
    <div className="relative">
      <Lock
        className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-faint"
        strokeWidth={2}
      />
      <input
        type="password"
        placeholder={placeholder}
        autoComplete={autoComplete}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border border-line bg-ink py-2.5 pl-9 pr-3 text-[13px] text-fg placeholder:text-faint transition-colors focus:border-cyan/60"
      />
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-obsidian px-5 py-10">
      <div aria-hidden className="pointer-events-none absolute inset-0 bg-grid" />
      <div
        aria-hidden
        className="pointer-events-none absolute left-1/2 top-[-10%] h-[32rem] w-[48rem] -translate-x-1/2 rounded-full bg-cyan/[0.07] blur-[130px]"
      />
      <Suspense fallback={<Spinner label="Loading…" />}>
        <ResetInner />
      </Suspense>
    </main>
  );
}
