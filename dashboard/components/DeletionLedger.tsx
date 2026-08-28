"use client";

// The account-deletion panel.
//
// Aegis reports a finding with the evidence behind it and a fix with the
// retest that proves it. Deletion is held to the same standard: instead of a
// red box asserting "this cannot be undone", it renders a statement of
// account — every class of thing that will be destroyed, itemized and counted
// from real rows, with dotted leaders and tabular figures so the numbers line
// up and read as a ledger rather than a warning.
//
// Zero rows stay visible but dimmed. "0 API tokens" is information; hiding it
// would leave the reader guessing whether it was counted at all.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Loader2, ShieldOff } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { useToast } from "@/components/Toast";
import { Button, Card, cn } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { clearTokens } from "@/lib/tokens";
import type { DeletionManifest, User } from "@/lib/types";

/** Ledger rows, in the order a person would reconstruct their account. */
const LINES: { key: keyof DeletionManifest; label: string }[] = [
  { key: "targets", label: "Targets" },
  { key: "scans", label: "Scans" },
  { key: "findings", label: "Findings" },
  { key: "triage_verdicts", label: "Triage verdicts" },
  { key: "share_links", label: "Report share links" },
  { key: "api_tokens", label: "API tokens" },
  { key: "installations", label: "GitHub App installations" },
];

export function DeletionLedger({ user }: { user: User }) {
  const router = useRouter();
  const toast = useToast();
  const queryClient = useQueryClient();

  const [open, setOpen] = useState(false);
  const [confirmEmail, setConfirmEmail] = useState("");
  const [password, setPassword] = useState("");

  const manifestQuery = useQuery({
    queryKey: ["account", "deletion-manifest"],
    queryFn: () => api.deletionManifest(),
    enabled: open,
  });

  const remove = useMutation({
    mutationFn: () =>
      api.deleteAccount({
        confirm_email: confirmEmail.trim(),
        password: password || null,
      }),
    onSuccess: () => {
      // Nothing left to be signed in to.
      queryClient.clear();
      clearTokens();
      router.replace("/login");
    },
    onError: (err) => toast.fromError(err, "Could not delete the account."),
  });

  const manifest = manifestQuery.data;
  const emailMatches =
    confirmEmail.trim().toLowerCase() === user.email.toLowerCase();
  // A GitHub-only account has no password to prove; asking for one would be
  // a field nobody can fill.
  const needsPassword = user.has_password;

  const error = remove.error instanceof ApiError ? remove.error : null;

  return (
    <section aria-labelledby="delete-account">
      <div className="mb-4 flex items-center gap-2.5">
        <ShieldOff className="h-4 w-4 text-danger" strokeWidth={2} />
        <h2
          id="delete-account"
          className="font-mono text-[11px] uppercase tracking-[0.14em] text-danger"
        >
          Delete account
        </h2>
      </div>

      <Card className="border-danger/25 p-5">
        {!open ? (
          <div className="flex flex-wrap items-center justify-between gap-4">
            <p className="max-w-md text-[13px] leading-relaxed text-muted">
              Deleting removes your account and every organization you are the
              only member of, with their scan history and findings. Review
              exactly what goes before you confirm.
            </p>
            <Button variant="danger" onClick={() => setOpen(true)}>
              Review what gets deleted
            </Button>
          </div>
        ) : manifestQuery.isLoading ? (
          <div className="flex items-center gap-2 text-[13px] text-muted">
            <Loader2 className="h-4 w-4 animate-spin" strokeWidth={2} />
            Counting what this would destroy…
          </div>
        ) : !manifest ? (
          <p className="text-[13px] text-danger">
            Could not work out what deleting this account would destroy. Nothing
            has been changed — try again in a moment.
          </p>
        ) : (
          <div className="space-y-6">
            {/* Blockers come first: refusing without saying how is a dead end. */}
            {manifest.blockers.length > 0 ? (
              <ul className="space-y-2.5">
                {manifest.blockers.map((blocker) => (
                  <li
                    key={blocker.code + blocker.message}
                    className="flex gap-2.5 rounded-lg border border-amber/30 bg-amber/[0.06] px-3.5 py-3"
                  >
                    <AlertTriangle
                      className="mt-0.5 h-4 w-4 shrink-0 text-amber"
                      strokeWidth={2}
                    />
                    <div className="space-y-1">
                      <p className="text-[13px] leading-relaxed text-amber">
                        {blocker.message}
                      </p>
                      <p className="text-[12px] leading-relaxed text-muted">
                        {blocker.action}
                      </p>
                    </div>
                  </li>
                ))}
              </ul>
            ) : null}

            <Ledger manifest={manifest} />

            {manifest.can_delete ? (
              <form
                className="space-y-3.5 border-t border-line pt-5"
                onSubmit={(e) => {
                  e.preventDefault();
                  if (emailMatches) remove.mutate();
                }}
              >
                <div>
                  <label
                    htmlFor="confirm-email"
                    className="mb-1.5 block text-[12px] text-muted"
                  >
                    Type{" "}
                    <span className="font-mono text-fg">{user.email}</span> to
                    confirm
                  </label>
                  <input
                    id="confirm-email"
                    value={confirmEmail}
                    onChange={(e) => setConfirmEmail(e.target.value)}
                    autoComplete="off"
                    spellCheck={false}
                    className="w-full rounded-lg border border-line bg-ink px-3 py-2.5 font-mono text-[13px] text-fg focus:border-danger/60 focus:outline-none"
                  />
                </div>

                {needsPassword ? (
                  <div>
                    <label
                      htmlFor="confirm-password"
                      className="mb-1.5 block text-[12px] text-muted"
                    >
                      Password
                    </label>
                    <input
                      id="confirm-password"
                      type="password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      autoComplete="current-password"
                      className="w-full rounded-lg border border-line bg-ink px-3 py-2.5 text-[13px] text-fg placeholder:text-faint focus:border-danger/60 focus:outline-none"
                    />
                  </div>
                ) : null}

                {error ? (
                  <p className="text-[12px] text-danger">{error.message}</p>
                ) : null}

                <div className="flex flex-wrap items-center justify-end gap-2.5">
                  <Button
                    type="button"
                    variant="ghost"
                    onClick={() => {
                      setOpen(false);
                      setConfirmEmail("");
                      setPassword("");
                    }}
                  >
                    Keep my account
                  </Button>
                  <Button
                    type="submit"
                    variant="danger"
                    loading={remove.isPending}
                    disabled={!emailMatches}
                  >
                    Delete account
                  </Button>
                </div>
              </form>
            ) : null}
          </div>
        )}
      </Card>
    </section>
  );
}

/* -------------------------------------------------------------------------- */
/** The statement of account. Dotted leaders carry the eye from label to count,
 *  the way an invoice does — the one place on this page allowed a flourish. */
function Ledger({ manifest }: { manifest: DeletionManifest }) {
  const destroys = manifest.organizations_deleted.length > 0;

  return (
    <div>
      <p className="mb-3 font-mono text-[10px] uppercase tracking-[0.14em] text-faint">
        What deletion destroys
      </p>

      {destroys ? (
        <dl className="space-y-0.5">
          <LedgerRow
            label={
              manifest.organizations_deleted.length === 1
                ? "Organization"
                : "Organizations"
            }
            value={manifest.organizations_deleted.join(", ")}
            emphasis
          />
          {LINES.map(({ key, label }) => (
            <LedgerRow
              key={key}
              label={label}
              value={manifest[key] as number}
              muted={(manifest[key] as number) === 0}
            />
          ))}
        </dl>
      ) : (
        <p className="text-[13px] leading-relaxed text-muted">
          Nothing is destroyed. You are not the only member of any organization,
          so only your seat is removed.
        </p>
      )}

      {manifest.running_scans > 0 ? (
        <p className="mt-3 text-[12px] leading-relaxed text-amber">
          {manifest.running_scans}{" "}
          {manifest.running_scans === 1 ? "scan is" : "scans are"} still running
          and will stop mid-flight.
        </p>
      ) : null}

      {manifest.organizations_left.length > 0 ? (
        <p className="mt-3 text-[12px] leading-relaxed text-muted">
          Kept, minus your seat: {manifest.organizations_left.join(", ")}.
        </p>
      ) : null}
    </div>
  );
}

function LedgerRow({
  label,
  value,
  muted,
  emphasis,
}: {
  label: string;
  value: string | number;
  muted?: boolean;
  emphasis?: boolean;
}) {
  return (
    <div className="flex items-baseline gap-2">
      <dt className={cn("text-[13px]", muted ? "text-faint" : "text-muted")}>
        {label}
      </dt>
      {/* The leader: a growing dotted rule between label and figure. */}
      <span
        aria-hidden
        className="min-w-4 flex-1 translate-y-[-3px] border-b border-dotted border-line"
      />
      <dd
        className={cn(
          "font-mono text-[13px] tabular-nums",
          emphasis ? "text-fg" : muted ? "text-faint" : "text-fg"
        )}
      >
        {value}
      </dd>
    </div>
  );
}
