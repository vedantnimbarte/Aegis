"use client";

// Account: who you are in Aegis, how you sign in, and how you leave.
//
// The page runs cool to hot. Identity and password are ordinary forms, held
// deliberately quiet, so the one loud thing on the page is the deletion
// ledger at the bottom — see components/DeletionLedger.tsx.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { AtSign, Check, Github, KeyRound, Loader2, UserRound } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { DeletionLedger } from "@/components/DeletionLedger";
import { useToast } from "@/components/Toast";
import { Button, Card, Pill, Spinner } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { formatDate } from "@/lib/format";
import type { User } from "@/lib/types";

const inputCls =
  "w-full rounded-lg border border-line bg-ink px-3 py-2.5 text-[13px] text-fg placeholder:text-faint focus:border-cyan/60 focus:outline-none";

function Section({
  icon: Icon,
  title,
  blurb,
  children,
}: {
  icon: typeof UserRound;
  title: string;
  blurb: string;
  children: React.ReactNode;
}) {
  const id = title.toLowerCase().replace(/\s+/g, "-");
  return (
    <section aria-labelledby={id}>
      <div className="mb-4 flex items-center gap-2.5">
        <Icon className="h-4 w-4 text-cyan-soft" strokeWidth={2} />
        <h2
          id={id}
          className="font-mono text-[11px] uppercase tracking-[0.14em] text-muted"
        >
          {title}
        </h2>
      </div>
      <Card className="p-5">
        <p className="mb-5 max-w-lg text-[13px] leading-relaxed text-muted">{blurb}</p>
        {children}
      </Card>
    </section>
  );
}

export default function AccountPage() {
  const { user } = useAuth();

  if (!user) return <Spinner label="Loading your account…" />;

  return (
    <>
      <header className="mb-8">
        <h1 className="font-display text-2xl font-bold text-fg">Account</h1>
        <p className="mt-1.5 text-[13px] text-muted">
          Signed in as <span className="font-mono text-fg">{user.email}</span> ·
          joined {formatDate(user.created_at)}
        </p>
      </header>

      <div className="space-y-10">
        <IdentitySection user={user} />
        <PasswordSection user={user} />
        <DeletionLedger user={user} />
      </div>
    </>
  );
}

/* -------------------------------------------------------------------------- */
function IdentitySection({ user }: { user: User }) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [name, setName] = useState(user.display_name ?? "");
  const [email, setEmail] = useState(user.email);

  const save = useMutation({
    mutationFn: () => {
      const body: { display_name?: string | null; email?: string } = {
        display_name: name.trim(),
      };
      if (email.trim().toLowerCase() !== user.email.toLowerCase()) {
        body.email = email.trim();
      }
      return api.updateProfile(body);
    },
    onSuccess: (updated) => {
      queryClient.invalidateQueries({ queryKey: ["me"] });
      toast.success(
        updated.email_verified
          ? "Profile saved."
          : "Profile saved. Check your inbox to confirm the new address."
      );
    },
    onError: (err) => toast.fromError(err, "Could not save your profile."),
  });

  const emailChanged = email.trim().toLowerCase() !== user.email.toLowerCase();
  const dirty = emailChanged || name.trim() !== (user.display_name ?? "");
  const error = save.error instanceof ApiError ? save.error.message : null;

  return (
    <Section
      icon={UserRound}
      title="Identity"
      blurb="Your name appears on reports and in your team's audit log. Your email is how you sign in and where scan results are sent."
    >
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          if (dirty) save.mutate();
        }}
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="display-name" className="mb-1.5 block text-[12px] text-muted">
              Name
            </label>
            <input
              id="display-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={120}
              placeholder={user.email.split("@")[0]}
              className={inputCls}
            />
          </div>
          <div>
            <label htmlFor="email" className="mb-1.5 block text-[12px] text-muted">
              Email
            </label>
            <div className="flex items-center gap-2">
              <input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className={`${inputCls} font-mono`}
              />
              {!emailChanged && user.email_verified ? (
                <Pill tone="border-signal/30 bg-signal/10 text-signal">
                  <Check className="h-3 w-3" strokeWidth={2.5} />
                  Verified
                </Pill>
              ) : null}
            </div>
          </div>
        </div>

        {emailChanged ? (
          <p className="flex items-start gap-2 rounded-lg border border-amber/30 bg-amber/[0.06] px-3 py-2.5 text-[12px] leading-relaxed text-amber">
            <AtSign className="mt-0.5 h-3.5 w-3.5 shrink-0" strokeWidth={2} />
            Saving sends a confirmation link to {email.trim()}. Until you follow
            it, scanning is paused — an unverified address can&apos;t authorize
            an attack.
          </p>
        ) : null}

        {user.github_username ? (
          <p className="flex items-center gap-2 text-[12px] text-faint">
            <Github className="h-3.5 w-3.5" strokeWidth={2} />
            Connected to GitHub as{" "}
            <span className="font-mono text-muted">{user.github_username}</span>
          </p>
        ) : null}

        {error ? <p className="text-[12px] text-danger">{error}</p> : null}

        <div className="flex justify-end">
          <Button type="submit" loading={save.isPending} disabled={!dirty}>
            Save changes
          </Button>
        </div>
      </form>
    </Section>
  );
}

/* -------------------------------------------------------------------------- */
function PasswordSection({ user }: { user: User }) {
  const toast = useToast();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");

  const change = useMutation({
    mutationFn: () =>
      api.changePassword({ current_password: current, new_password: next }),
    onSuccess: () => {
      setCurrent("");
      setNext("");
      toast.success("Password changed.");
    },
    onError: (err) => toast.fromError(err, "Could not change your password."),
  });

  const error = change.error instanceof ApiError ? change.error.message : null;
  const tooShort = next.length > 0 && next.length < 8;
  const ready = current.length > 0 && next.length >= 8;

  // A GitHub-only account has no current password to prove. Offering the form
  // anyway would be a dead end, so it points at the flow that does work.
  if (!user.has_password) {
    return (
      <Section
        icon={KeyRound}
        title="Password"
        blurb="This account signs in with GitHub, so it has no password."
      >
        <Link
          href="/forgot-password"
          className="text-[13px] font-medium text-cyan-soft hover:text-cyan"
        >
          Set a password by email →
        </Link>
      </Section>
    );
  }

  return (
    <Section
      icon={KeyRound}
      title="Password"
      blurb="Changing your password does not sign you out of other sessions."
    >
      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          if (ready) change.mutate();
        }}
      >
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label
              htmlFor="current-password"
              className="mb-1.5 block text-[12px] text-muted"
            >
              Current password
            </label>
            <input
              id="current-password"
              type="password"
              autoComplete="current-password"
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
              className={inputCls}
            />
          </div>
          <div>
            <label
              htmlFor="new-password"
              className="mb-1.5 block text-[12px] text-muted"
            >
              New password
            </label>
            <input
              id="new-password"
              type="password"
              autoComplete="new-password"
              value={next}
              onChange={(e) => setNext(e.target.value)}
              aria-describedby="password-hint"
              className={inputCls}
            />
            <p
              id="password-hint"
              className={`mt-1.5 text-[11px] ${tooShort ? "text-amber" : "text-faint"}`}
            >
              At least 8 characters.
            </p>
          </div>
        </div>

        {error ? <p className="text-[12px] text-danger">{error}</p> : null}

        <div className="flex justify-end">
          <Button type="submit" disabled={!ready || change.isPending}>
            {change.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" strokeWidth={2} />
            ) : null}
            Change password
          </Button>
        </div>
      </form>
    </Section>
  );
}
