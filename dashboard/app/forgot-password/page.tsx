"use client";

import { useMutation } from "@tanstack/react-query";
import { ArrowLeft, Check, Mail, ShieldHalf } from "lucide-react";
import Link from "next/link";
import { useState, type FormEvent } from "react";

import { api, ApiError } from "@/lib/api";
import { Button } from "@/components/ui";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const request = useMutation({
    mutationFn: () => api.forgotPassword(email.trim()),
  });

  function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setFormError(null);
    if (!EMAIL_RE.test(email.trim())) {
      setFormError("Enter a valid email address.");
      return;
    }
    request.mutate();
  }

  const errorMessage =
    formError ||
    (request.error instanceof ApiError
      ? request.error.message
      : request.error
        ? "Something went wrong. Please try again."
        : null);

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
            Reset your password
          </h1>
          <p className="mt-2 text-[13px] leading-relaxed text-muted">
            Enter your email and we&rsquo;ll send you a link to reset it.
          </p>
        </div>

        <div className="rounded-2xl border border-line bg-surface/50 p-6">
          {request.isSuccess ? (
            <div className="flex flex-col items-center gap-3 py-2 text-center">
              <span className="grid h-10 w-10 place-items-center rounded-full bg-signal/15 text-signal">
                <Check className="h-5 w-5" strokeWidth={2.5} />
              </span>
              <p className="text-[13px] leading-relaxed text-muted">
                {request.data?.detail ??
                  "If an account exists for that email, a reset link is on its way."}
              </p>
            </div>
          ) : (
            <form onSubmit={onSubmit} noValidate className="space-y-3">
              <div className="relative">
                <Mail
                  className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-faint"
                  strokeWidth={2}
                />
                <input
                  type="email"
                  placeholder="you@company.com"
                  autoComplete="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full rounded-lg border border-line bg-ink py-2.5 pl-9 pr-3 text-[13px] text-fg placeholder:text-faint transition-colors focus:border-cyan/60"
                />
              </div>

              {errorMessage ? (
                <p className="rounded-lg border border-danger/30 bg-danger/[0.06] px-3 py-2.5 text-[12px] text-danger">
                  {errorMessage}
                </p>
              ) : null}

              <Button type="submit" className="w-full" loading={request.isPending}>
                Send reset link
              </Button>
            </form>
          )}

          <Link
            href="/login"
            className="mt-5 flex items-center justify-center gap-1.5 text-[12px] font-medium text-muted hover:text-fg"
          >
            <ArrowLeft className="h-3.5 w-3.5" strokeWidth={2} />
            Back to sign in
          </Link>
        </div>
      </div>
    </main>
  );
}
