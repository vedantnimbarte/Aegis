"use client";

import { AlertTriangle, Loader2, ShieldHalf } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";

import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";

function CallbackInner() {
  const router = useRouter();
  const params = useSearchParams();
  const { login } = useAuth();
  const [error, setError] = useState<string | null>(null);
  const ran = useRef(false); // guard against React 18 StrictMode double-invoke

  useEffect(() => {
    if (ran.current) return;
    ran.current = true;

    const code = params.get("code");
    const state = params.get("state");
    const oauthError = params.get("error");

    if (oauthError) {
      setError(params.get("error_description") || "GitHub sign-in was cancelled.");
      return;
    }
    if (!code) {
      setError("No authorization code was returned by GitHub.");
      return;
    }

    // CSRF: the state we get back must match the one we generated.
    const expected = window.sessionStorage.getItem("aegis.oauth_state");
    window.sessionStorage.removeItem("aegis.oauth_state");
    if (expected && state && expected !== state) {
      setError("Sign-in could not be verified (state mismatch). Please try again.");
      return;
    }

    const redirectUri = process.env.NEXT_PUBLIC_GITHUB_REDIRECT_URI || undefined;
    api
      .githubAuth(code, redirectUri, state ?? undefined)
      .then((token) => {
        login(token);
        router.replace("/");
      })
      .catch((err) => {
        setError(
          err instanceof ApiError ? err.message : "Could not complete sign-in. Please try again."
        );
      });
  }, [params, login, router]);

  if (error) {
    return (
      <div className="w-full max-w-sm text-center">
        <span className="mx-auto mb-5 grid h-12 w-12 place-items-center rounded-xl border border-danger/40 bg-danger/10 text-danger">
          <AlertTriangle className="h-6 w-6" strokeWidth={2} />
        </span>
        <h1 className="font-display text-xl font-bold text-fg">Sign-in failed</h1>
        <p className="mt-2 text-[13px] leading-relaxed text-muted">{error}</p>
        <Link
          href="/login"
          className="mt-6 inline-flex items-center justify-center rounded-lg bg-cyan px-4 py-2.5 font-display text-[13px] font-semibold text-obsidian hover:bg-cyan-soft"
        >
          Back to sign in
        </Link>
      </div>
    );
  }

  return (
    <div className="flex flex-col items-center gap-4 text-center">
      <span className="grid h-12 w-12 place-items-center rounded-xl border border-cyan/40 bg-cyan/10 text-cyan-soft">
        <ShieldHalf className="h-6 w-6" strokeWidth={2} />
      </span>
      <div className="flex items-center gap-2 text-[13px] text-muted">
        <Loader2 className="h-4 w-4 animate-spin" strokeWidth={2} />
        Completing sign-in…
      </div>
    </div>
  );
}

export default function CallbackPage() {
  return (
    <main className="flex min-h-screen items-center justify-center bg-obsidian px-5">
      <Suspense
        fallback={
          <div className="flex items-center gap-2 text-[13px] text-muted">
            <Loader2 className="h-4 w-4 animate-spin" strokeWidth={2} />
            Loading…
          </div>
        }
      >
        <CallbackInner />
      </Suspense>
    </main>
  );
}
