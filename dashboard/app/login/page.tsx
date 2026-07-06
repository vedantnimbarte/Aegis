"use client";

import { Github, ShieldHalf } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { useAuth } from "@/lib/auth";
import { buildGitHubAuthUrl } from "@/lib/format";
import { Button } from "@/components/ui";

export default function LoginPage() {
  const router = useRouter();
  const { isAuthenticated } = useAuth();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);
  useEffect(() => {
    if (mounted && isAuthenticated) router.replace("/");
  }, [mounted, isAuthenticated, router]);

  const clientId = process.env.NEXT_PUBLIC_GITHUB_CLIENT_ID;

  function signIn() {
    window.location.href = buildGitHubAuthUrl();
  }

  return (
    <main className="relative flex min-h-screen items-center justify-center overflow-hidden bg-obsidian px-5">
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
            Sign in to Aegis
          </h1>
          <p className="mt-2 text-[13px] leading-relaxed text-muted">
            Connect your GitHub account to run continuous AI penetration tests on your
            repositories.
          </p>
        </div>

        <div className="rounded-2xl border border-line bg-surface/50 p-6">
          <Button icon={Github} className="w-full" onClick={signIn} disabled={!clientId}>
            Continue with GitHub
          </Button>

          {!clientId ? (
            <p className="mt-4 rounded-lg border border-amber/30 bg-amber/[0.06] px-3 py-2.5 font-mono text-[11px] leading-relaxed text-amber">
              NEXT_PUBLIC_GITHUB_CLIENT_ID is not set. Add it to the dashboard&rsquo;s
              environment to enable sign-in.
            </p>
          ) : (
            <p className="mt-4 text-center font-mono text-[11px] leading-relaxed text-faint">
              Read-only access to your repositories. We never write without your approval.
            </p>
          )}
        </div>
      </div>
    </main>
  );
}
