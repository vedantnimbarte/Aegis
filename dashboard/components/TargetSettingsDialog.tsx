"use client";

// Per-target guardrails and merge policy.
//
// The pull-request gate lives here rather than in a global setting because
// one noisy legacy service should be able to warn instead of block without
// weakening the gate everywhere else.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Settings2, X } from "lucide-react";
import { useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";
import type { Target } from "@/lib/types";
import { Button, ErrorState } from "./ui";

const SEVERITIES = ["critical", "high", "medium", "low"] as const;

export function TargetSettingsDialog({
  target,
  onClose,
}: {
  target: Target;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();

  const [newOnly, setNewOnly] = useState(target.gate_new_findings_only);
  const [blocking, setBlocking] = useState<string[]>(
    (target.gate_fail_severities ?? "critical,high")
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean)
  );
  const [budget, setBudget] = useState(
    target.max_budget_usd == null ? "" : String(target.max_budget_usd)
  );
  const [url, setUrl] = useState(target.url ?? "");
  const [discovery, setDiscovery] = useState(target.discovery_enabled);

  const mutation = useMutation({
    mutationFn: () =>
      api.updateTarget(target.id, {
        gate_new_findings_only: newOnly,
        gate_fail_severities: blocking.join(","),
        max_budget_usd: budget.trim() === "" ? null : Number(budget),
        url: url.trim() || null,
        discovery_enabled: discovery,
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["targets"] });
      onClose();
    },
  });

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const toggle = (severity: string) =>
    setBlocking((current) =>
      current.includes(severity)
        ? current.filter((s) => s !== severity)
        : [...current, severity]
    );

  const errorMessage =
    mutation.error instanceof ApiError
      ? mutation.error.message
      : mutation.error
        ? "Could not save these settings."
        : null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-end justify-center bg-obsidian/70 p-4 backdrop-blur-sm sm:items-center"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
    >
      <div
        className="w-full max-w-lg overflow-hidden rounded-2xl border border-line bg-surface shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-line px-5 py-4">
          <div className="flex min-w-0 items-center gap-2.5">
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-lg border border-cyan/40 bg-cyan/10 text-cyan-soft">
              <Settings2 className="h-4 w-4" strokeWidth={2} />
            </span>
            <h2 className="truncate font-display text-[15px] font-semibold text-fg">
              {target.name}
            </h2>
          </div>
          <button
            onClick={onClose}
            aria-label="Close"
            className="grid h-8 w-8 place-items-center rounded-lg text-faint hover:bg-ink hover:text-fg"
          >
            <X className="h-4 w-4" strokeWidth={2} />
          </button>
        </div>

        <div className="space-y-5 px-5 py-5">
          {/* A live URL is what makes retesting possible on a repo target:
              re-reading the same source proves the fix looks right, which is
              exactly the claim verification exists to replace. */}
          <div>
            <label className="mb-1.5 block font-mono text-[11px] uppercase tracking-wide text-faint">
              Live URL <span className="text-faint/70">(optional)</span>
            </label>
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://app.example.com"
              className="w-full rounded-lg border border-line bg-ink px-3 py-2.5 font-mono text-[13px] text-fg placeholder:text-faint focus:border-cyan/60"
            />
            <p className="mt-1.5 text-[11px] leading-relaxed text-faint">
              Needed to verify a fix: retesting re-runs the exploit against a
              running system.
            </p>
          </div>

          <div>
            <span className="mb-1.5 block font-mono text-[11px] uppercase tracking-wide text-faint">
              Pull-request gate
            </span>
            <label className="flex items-start gap-2.5 rounded-lg border border-line bg-ink px-3 py-2.5">
              <input
                type="checkbox"
                checked={newOnly}
                onChange={(e) => setNewOnly(e.target.checked)}
                className="mt-0.5 h-4 w-4 shrink-0 accent-cyan"
              />
              <span className="text-[12px] leading-relaxed text-muted">
                Only fail on findings this pull request introduced. Existing
                findings are still reported, never blocking — a gate that fails
                on the backlog gets switched off in week two.
              </span>
            </label>

            <div className="mt-2.5 flex flex-wrap gap-2">
              {SEVERITIES.map((severity) => (
                <button
                  key={severity}
                  type="button"
                  onClick={() => toggle(severity)}
                  className={
                    "rounded-lg border px-3 py-1.5 font-mono text-[11px] capitalize transition-colors " +
                    (blocking.includes(severity)
                      ? "border-cyan/50 bg-cyan/10 text-cyan-soft"
                      : "border-line bg-ink text-faint hover:border-line/80")
                  }
                >
                  {severity}
                </button>
              ))}
            </div>
            <p className="mt-1.5 text-[11px] text-faint">
              {blocking.length === 0
                ? "Nothing blocks — findings are reported only."
                : "Blocks a merge at: " + blocking.join(", ") + "."}
            </p>
          </div>

          <div>
            <label className="mb-1.5 block font-mono text-[11px] uppercase tracking-wide text-faint">
              Spend cap per scan <span className="text-faint/70">(optional)</span>
            </label>
            <input
              value={budget}
              onChange={(e) => setBudget(e.target.value)}
              inputMode="decimal"
              placeholder="Platform default"
              className="w-full rounded-lg border border-line bg-ink px-3 py-2.5 font-mono text-[13px] text-fg placeholder:text-faint focus:border-cyan/60"
            />
            <p className="mt-1.5 text-[11px] leading-relaxed text-faint">
              US dollars of LLM spend. A large monorepo can be bounded here
              without lowering the ceiling for everything else.
            </p>
          </div>

          <label className="flex items-start gap-2.5 rounded-lg border border-line bg-ink px-3 py-2.5">
            <input
              type="checkbox"
              checked={discovery}
              onChange={(e) => setDiscovery(e.target.checked)}
              className="mt-0.5 h-4 w-4 shrink-0 accent-cyan"
            />
            <span className="text-[12px] leading-relaxed text-muted">
              Watch this domain for new hosts and tell me when something
              appears.
            </span>
          </label>

          {errorMessage ? <ErrorState message={errorMessage} /> : null}
        </div>

        <div className="flex items-center justify-end gap-2.5 border-t border-line px-5 py-4">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button loading={mutation.isPending} onClick={() => mutation.mutate()}>
            Save
          </Button>
        </div>
      </div>
    </div>
  );
}
