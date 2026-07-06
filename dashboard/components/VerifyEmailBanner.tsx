"use client";

// A dismissible-free banner shown across the dashboard while the signed-in
// user's email is unverified. Scanning and connecting repos stay gated until
// they verify; this nudges them and offers a one-click resend.

import { useMutation } from "@tanstack/react-query";
import { MailWarning } from "lucide-react";

import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export function VerifyEmailBanner() {
  const { user } = useAuth();

  const resend = useMutation({ mutationFn: () => api.resendVerification() });

  // Only for signed-in, unverified users.
  if (!user || user.email_verified) return null;

  return (
    <div className="mb-6 flex flex-col gap-2 rounded-xl border border-amber/30 bg-amber/[0.07] px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-start gap-2.5">
        <MailWarning className="mt-0.5 h-4 w-4 shrink-0 text-amber" strokeWidth={2} />
        <p className="text-[13px] leading-relaxed text-fg">
          Verify your email{" "}
          <span className="font-mono text-amber">{user.email}</span> to start
          scanning. Check your inbox for the link.
        </p>
      </div>
      <div className="shrink-0 pl-6 sm:pl-0">
        {resend.isSuccess ? (
          <span className="text-[12px] font-medium text-signal">Verification email sent.</span>
        ) : (
          <button
            onClick={() => resend.mutate()}
            disabled={resend.isPending}
            className="text-[12px] font-semibold text-amber transition-colors hover:text-amber/80 disabled:opacity-60"
          >
            {resend.isPending ? "Sending…" : "Resend email"}
          </button>
        )}
      </div>
    </div>
  );
}
