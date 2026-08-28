"use client";

// Add a target that is not a source repository: a live web app, an API, an
// LLM endpoint, or an MCP server.
//
// Repositories are connected from the source-host list instead, because
// connecting one requires proving write access on the host — a URL you type
// here is attested for by the scan authorization terms.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Crosshair, X } from "lucide-react";
import { useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";
import type { TargetKind } from "@/lib/types";
import { Button, ErrorState } from "./ui";

const KINDS: { value: TargetKind; title: string; blurb: string }[] = [
  { value: "web", title: "Web app", blurb: "A running application" },
  { value: "api", title: "API", blurb: "An HTTP API or service" },
  { value: "llm", title: "LLM app", blurb: "A chat or completion endpoint" },
  { value: "mcp", title: "MCP server", blurb: "Tools exposed to an agent" },
];

export function AddTargetDialog({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const [kind, setKind] = useState<TargetKind>("web");
  const [url, setUrl] = useState("");
  const [name, setName] = useState("");
  const [discovery, setDiscovery] = useState(false);

  const mutation = useMutation({
    mutationFn: () =>
      api.createTarget({
        kind,
        url: url.trim(),
        name: name.trim() || null,
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

  const errorMessage =
    mutation.error instanceof ApiError
      ? mutation.error.message
      : mutation.error
        ? "Could not add that target. Try again."
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
              <Crosshair className="h-4 w-4" strokeWidth={2} />
            </span>
            <h2 className="font-display text-[15px] font-semibold text-fg">Add a target</h2>
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
          <div>
            <label className="mb-1.5 block font-mono text-[11px] uppercase tracking-wide text-faint">
              What is it
            </label>
            <div className="grid grid-cols-2 gap-2">
              {KINDS.map((k) => (
                <button
                  key={k.value}
                  type="button"
                  onClick={() => setKind(k.value)}
                  className={
                    "rounded-lg border px-3 py-2.5 text-left transition-colors " +
                    (kind === k.value
                      ? "border-cyan/50 bg-cyan/10"
                      : "border-line bg-ink hover:border-line/80")
                  }
                >
                  <span className="block font-display text-[13px] font-semibold text-fg">
                    {k.title}
                  </span>
                  <span className="mt-0.5 block text-[11px] leading-tight text-muted">
                    {k.blurb}
                  </span>
                </button>
              ))}
            </div>
          </div>

          <div>
            <label className="mb-1.5 block font-mono text-[11px] uppercase tracking-wide text-faint">
              URL
            </label>
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://app.example.com"
              className="w-full rounded-lg border border-line bg-ink px-3 py-2.5 font-mono text-[13px] text-fg placeholder:text-faint focus:border-cyan/60"
            />
          </div>

          <div>
            <label className="mb-1.5 block font-mono text-[11px] uppercase tracking-wide text-faint">
              Name <span className="text-faint/70">(optional)</span>
            </label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="Defaults to the hostname"
              className="w-full rounded-lg border border-line bg-ink px-3 py-2.5 text-[13px] text-fg placeholder:text-faint focus:border-cyan/60"
            />
          </div>

          {kind === "web" || kind === "api" ? (
            <label className="flex items-start gap-2.5 rounded-lg border border-line bg-ink px-3 py-2.5">
              <input
                type="checkbox"
                checked={discovery}
                onChange={(e) => setDiscovery(e.target.checked)}
                className="mt-0.5 h-4 w-4 shrink-0 accent-cyan"
              />
              <span className="text-[12px] leading-relaxed text-muted">
                Watch this domain for new hosts. Aegis checks certificate
                transparency daily and tells you when something appears —
                discovered hosts are never scanned automatically.
              </span>
            </label>
          ) : null}

          <p className="rounded-lg border border-amber/30 bg-amber/[0.06] px-3 py-2.5 text-[12px] leading-relaxed text-amber">
            Only add systems you own or are explicitly authorized to test.
            Scanning is an active attack, not a passive check.
          </p>

          {errorMessage ? <ErrorState message={errorMessage} /> : null}
        </div>

        <div className="flex items-center justify-end gap-2.5 border-t border-line px-5 py-4">
          <Button variant="ghost" onClick={onClose}>
            Cancel
          </Button>
          <Button
            icon={Crosshair}
            loading={mutation.isPending}
            disabled={!url.trim()}
            onClick={() => mutation.mutate()}
          >
            Add target
          </Button>
        </div>
      </div>
    </div>
  );
}
