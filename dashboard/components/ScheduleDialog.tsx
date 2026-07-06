"use client";

// Configure (or edit) recurring scans for a single repository: cadence, depth,
// custom instructions, and an enabled toggle. Create or update in place; an
// existing schedule can also be deleted.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { CalendarClock, Trash2, X } from "lucide-react";
import { useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";
import type { Repository, ScanFrequency, ScanMode, Schedule } from "@/lib/types";
import { Button, ErrorState } from "./ui";

const FREQUENCIES: { value: ScanFrequency; label: string }[] = [
  { value: "daily", label: "Daily" },
  { value: "weekly", label: "Weekly" },
  { value: "monthly", label: "Monthly" },
];

const MODES: { value: ScanMode; label: string }[] = [
  { value: "quick", label: "Quick" },
  { value: "standard", label: "Standard" },
  { value: "deep", label: "Deep" },
];

export function ScheduleDialog({
  repository,
  existing,
  onClose,
}: {
  repository: Repository;
  existing: Schedule | null;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();

  const [frequency, setFrequency] = useState<ScanFrequency>(existing?.frequency ?? "weekly");
  const [mode, setMode] = useState<ScanMode>(existing?.scan_mode ?? "quick");
  const [instructions, setInstructions] = useState(existing?.custom_instructions ?? "");
  const [enabled, setEnabled] = useState(existing?.enabled ?? true);

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["schedules"] });

  const save = useMutation({
    mutationFn: () =>
      existing
        ? api.updateSchedule(existing.id, {
            frequency,
            scan_mode: mode,
            custom_instructions: instructions.trim() || null,
            enabled,
          })
        : api.createSchedule({
            repository_id: repository.id,
            frequency,
            scan_mode: mode,
            custom_instructions: instructions.trim() || null,
          }),
    onSuccess: () => {
      refresh();
      onClose();
    },
  });

  const remove = useMutation({
    mutationFn: () => api.deleteSchedule(existing!.id),
    onSuccess: () => {
      refresh();
      onClose();
    },
  });

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const error =
    save.error instanceof ApiError
      ? save.error.message
      : remove.error instanceof ApiError
        ? remove.error.message
        : save.error || remove.error
          ? "Something went wrong. Please try again."
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
              <CalendarClock className="h-4 w-4" strokeWidth={2} />
            </span>
            <div>
              <h2 className="font-display text-[15px] font-semibold text-fg">
                {existing ? "Edit schedule" : "Recurring scans"}
              </h2>
              <p className="truncate font-mono text-[11px] text-faint">{repository.name}</p>
            </div>
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
          {/* Frequency */}
          <div>
            <label className="mb-1.5 block font-mono text-[11px] uppercase tracking-wide text-faint">
              Frequency
            </label>
            <div className="grid grid-cols-3 gap-2">
              {FREQUENCIES.map((f) => (
                <button
                  key={f.value}
                  type="button"
                  onClick={() => setFrequency(f.value)}
                  className={
                    "rounded-lg border px-3 py-2.5 font-display text-[13px] font-semibold transition-colors " +
                    (frequency === f.value
                      ? "border-cyan/50 bg-cyan/10 text-fg"
                      : "border-line bg-ink text-muted hover:text-fg")
                  }
                >
                  {f.label}
                </button>
              ))}
            </div>
          </div>

          {/* Depth */}
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
                    "rounded-lg border px-3 py-2.5 font-display text-[13px] font-semibold transition-colors " +
                    (mode === m.value
                      ? "border-cyan/50 bg-cyan/10 text-fg"
                      : "border-line bg-ink text-muted hover:text-fg")
                  }
                >
                  {m.label}
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
              rows={2}
              placeholder="e.g. Focus on authentication and IDOR."
              className="w-full resize-none rounded-lg border border-line bg-ink px-3 py-2.5 text-[13px] text-fg placeholder:text-faint focus:border-cyan/60"
            />
          </div>

          {/* Enabled toggle (edit only) */}
          {existing ? (
            <label className="flex items-center justify-between rounded-lg border border-line bg-ink px-3 py-2.5">
              <span className="text-[13px] text-fg">Schedule enabled</span>
              <input
                type="checkbox"
                checked={enabled}
                onChange={(e) => setEnabled(e.target.checked)}
                className="h-4 w-4 accent-cyan"
              />
            </label>
          ) : (
            <p className="text-[11px] leading-relaxed text-faint">
              The first scan runs one {frequency.replace(/ly$/, "")} from now, then repeats.
            </p>
          )}

          {error ? <ErrorState message={error} /> : null}
        </div>

        <div className="flex items-center justify-between gap-2.5 border-t border-line px-5 py-4">
          {existing ? (
            <Button
              variant="danger"
              icon={Trash2}
              loading={remove.isPending}
              onClick={() => remove.mutate()}
            >
              Delete
            </Button>
          ) : (
            <span />
          )}
          <div className="flex items-center gap-2.5">
            <Button variant="ghost" onClick={onClose}>
              Cancel
            </Button>
            <Button icon={CalendarClock} loading={save.isPending} onClick={() => save.mutate()}>
              {existing ? "Save" : "Schedule"}
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}
