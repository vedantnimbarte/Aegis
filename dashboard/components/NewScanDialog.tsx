"use client";

// Modal for launching a Strix scan: pick a connected repo, a scan depth, and
// optional custom instructions. On success it routes to the new scan's report.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Radar, X } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";
import type { Repository, ScanMode } from "@/lib/types";
import { Button, ErrorState } from "./ui";

const MODES: { value: ScanMode; title: string; blurb: string }[] = [
  { value: "quick", title: "Quick", blurb: "Fast pass for CI parity" },
  { value: "standard", title: "Standard", blurb: "Balanced depth & coverage" },
  { value: "deep", title: "Deep", blurb: "Exhaustive, business-logic aware" },
];

export function NewScanDialog({
  repositories,
  defaultRepoId,
  onClose,
}: {
  repositories: Repository[];
  defaultRepoId?: string;
  onClose: () => void;
}) {
  const router = useRouter();
  const queryClient = useQueryClient();

  const [repositoryId, setRepositoryId] = useState(
    defaultRepoId ?? repositories[0]?.id ?? ""
  );
  const [mode, setMode] = useState<ScanMode>("standard");
  const [instructions, setInstructions] = useState("");

  const mutation = useMutation({
    mutationFn: () =>
      api.createScan({
        repository_id: repositoryId,
        scan_mode: mode,
        custom_instructions: instructions.trim() || null,
      }),
    onSuccess: (scan) => {
      queryClient.invalidateQueries({ queryKey: ["scans"] });
      onClose();
      router.push(`/scans/${scan.id}`);
    },
  });

  // Close on Escape.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const errorMessage =
    mutation.error instanceof ApiError
      ? mutation.error.message
      : mutation.error
        ? "Could not launch the scan. Try again."
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
          <div className="flex items-center gap-2.5">
            <span className="grid h-8 w-8 place-items-center rounded-lg border border-cyan/40 bg-cyan/10 text-cyan-soft">
              <Radar className="h-4 w-4" strokeWidth={2} />
            </span>
            <h2 className="font-display text-[15px] font-semibold text-fg">New scan</h2>
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
          {/* Repository */}
          <div>
            <label className="mb-1.5 block font-mono text-[11px] uppercase tracking-wide text-faint">
              Repository
            </label>
            <select
              value={repositoryId}
              onChange={(e) => setRepositoryId(e.target.value)}
              className="w-full rounded-lg border border-line bg-ink px-3 py-2.5 text-[13px] text-fg focus:border-cyan/60"
            >
              {repositories.map((r) => (
                <option key={r.id} value={r.id}>
                  {r.name}
                </option>
              ))}
            </select>
          </div>

          {/* Scan mode */}
          <div>
            <label className="mb-1.5 block font-mono text-[11px] uppercase tracking-wide text-faint">
              Depth
            </label>
            <div className="grid grid-cols-3 gap-2">
              {MODES.map((m) => (
                <button
                  key={m.value}
                  type="button"
                  onClick={() => setMode(m.value)}
                  className={
                    "rounded-lg border px-3 py-2.5 text-left transition-colors " +
                    (mode === m.value
                      ? "border-cyan/50 bg-cyan/10"
                      : "border-line bg-ink hover:border-line/80")
                  }
                >
                  <span className="block font-display text-[13px] font-semibold text-fg">
                    {m.title}
                  </span>
                  <span className="mt-0.5 block text-[11px] leading-tight text-muted">
                    {m.blurb}
                  </span>
                </button>
              ))}
            </div>
          </div>

          {/* Instructions */}
          <div>
            <label className="mb-1.5 block font-mono text-[11px] uppercase tracking-wide text-faint">
              Custom instructions <span className="text-faint/70">(optional)</span>
            </label>
            <textarea
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              rows={3}
              placeholder="e.g. Focus on authentication, IDOR, and business-logic flaws."
              className="w-full resize-none rounded-lg border border-line bg-ink px-3 py-2.5 text-[13px] text-fg placeholder:text-faint focus:border-cyan/60"
            />
          </div>

          {errorMessage ? <ErrorState message={errorMessage} /> : null}
        </div>

        <div className="flex items-center justify-end gap-2.5 border-t border-line px-5 py-4">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            icon={Radar}
            loading={mutation.isPending}
            disabled={!repositoryId}
            onClick={() => mutation.mutate()}
          >
            Launch pentest
          </Button>
        </div>
      </div>
    </div>
  );
}
