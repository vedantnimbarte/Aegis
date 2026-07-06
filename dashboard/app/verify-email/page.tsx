"use client";

import { AlertTriangle, Check, Loader2, ShieldHalf } from "lucide-react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";

import { api, ApiError } from "@/lib/api";

type State = "verifying" | "success" | "error";

function VerifyInner() {
  const params = useSearchParams();
  const [state, setState] = useState<State>("verifying");
  const [message, setMessage] = useState("");
  const ran = useRef(false); // guard React 18 StrictMode double-invoke

  useEffect(() => {
    if (ran.current) return;
    ran.current = true;

    const token = params.get("token");
    if (!token) {
      setState("error");
      setMessage("This verification link is missing its token.");
      return;
    }
    api
      .verifyEmail(token)
      .then((res) => {
        setState("success");
        setMessage(res.detail ?? "Your email has been verified.");
      })
      .catch((err) => {
        setState("error");
        setMessage(
          err instanceof ApiError
            ? err.message
            : "Could not verify your email. Please try again."
        );
      });
  }, [params]);

  if (state === "verifying") {
    return (
      <Center>
        <span className="grid h-12 w-12 place-items-center rounded-xl border border-cyan/40 bg-cyan/10 text-cyan-soft">
          <ShieldHalf className="h-6 w-6" strokeWidth={2} />
        </span>
        <div className="flex items-center gap-2 text-[13px] text-muted">
          <Loader2 className="h-4 w-4 animate-spin" strokeWidth={2} />
          Verifying your email…
        </div>
      </Center>
    );
  }

  const ok = state === "success";
  return (
    <Center>
      <span
        className={
          "grid h-12 w-12 place-items-center rounded-xl border " +
          (ok
            ? "border-signal/40 bg-signal/10 text-signal"
            : "border-danger/40 bg-danger/10 text-danger")
        }
      >
        {ok ? (
          <Check className="h-6 w-6" strokeWidth={2.5} />
        ) : (
          <AlertTriangle className="h-6 w-6" strokeWidth={2} />
        )}
      </span>
      <h1 className="font-display text-xl font-bold text-fg">
        {ok ? "Email verified" : "Verification failed"}
      </h1>
      <p className="max-w-xs text-[13px] leading-relaxed text-muted">{message}</p>
      <Link
        href="/"
        className="mt-2 inline-flex items-center justify-center rounded-lg bg-cyan px-4 py-2.5 font-display text-[13px] font-semibold text-obsidian hover:bg-cyan-soft"
      >
        Go to dashboard
      </Link>
    </Center>
  );
}

function Center({ children }: { children: React.ReactNode }) {
  return (
    <div className="relative z-10 flex w-full max-w-sm flex-col items-center gap-4 rounded-2xl border border-line bg-surface/50 p-8 text-center">
      {children}
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-obsidian px-5 py-10">
      <div aria-hidden className="pointer-events-none absolute inset-0 bg-grid" />
      <div
        aria-hidden
        className="pointer-events-none absolute left-1/2 top-[-10%] h-[32rem] w-[48rem] -translate-x-1/2 rounded-full bg-cyan/[0.07] blur-[130px]"
      />
      <Suspense
        fallback={
          <div className="flex items-center gap-2 text-[13px] text-muted">
            <Loader2 className="h-4 w-4 animate-spin" strokeWidth={2} />
            Loading…
          </div>
        }
      >
        <VerifyInner />
      </Suspense>
    </main>
  );
}
