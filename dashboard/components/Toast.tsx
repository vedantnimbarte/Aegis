"use client";

// App-wide toasts. Writes (triage verdicts, issue creation, repo connects) used
// to succeed silently and fail in four different shapes; this is the one place
// both outcomes are reported.

import { Check, X, AlertTriangle } from "lucide-react";
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

import { ApiError } from "@/lib/api";
import { cn } from "./ui";

type ToastTone = "success" | "error";

interface Toast {
  id: number;
  tone: ToastTone;
  message: string;
}

interface ToastApi {
  success: (message: string) => void;
  error: (message: string) => void;
  /** Report a caught error, preferring the API's own message when there is one. */
  fromError: (err: unknown, fallback: string) => void;
}

const ToastContext = createContext<ToastApi | null>(null);

const DISMISS_AFTER_MS = 5000;
let nextId = 0;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);

  const dismiss = useCallback((id: number) => {
    setToasts((current) => current.filter((t) => t.id !== id));
  }, []);

  const push = useCallback((tone: ToastTone, message: string) => {
    const id = nextId++;
    setToasts((current) => [...current, { id, tone, message }]);
  }, []);

  const api = useMemo<ToastApi>(
    () => ({
      success: (message) => push("success", message),
      error: (message) => push("error", message),
      fromError: (err, fallback) =>
        push("error", err instanceof ApiError ? err.message : fallback),
    }),
    [push]
  );

  return (
    <ToastContext.Provider value={api}>
      {children}
      <div
        // `polite` so a success doesn't interrupt whatever is being read; the
        // toasts are confirmations, not alarms.
        aria-live="polite"
        className="pointer-events-none fixed inset-x-4 bottom-4 z-50 flex flex-col items-center gap-2 sm:inset-x-auto sm:right-6 sm:items-end"
      >
        {toasts.map((toast) => (
          <ToastRow key={toast.id} toast={toast} onDismiss={() => dismiss(toast.id)} />
        ))}
      </div>
    </ToastContext.Provider>
  );
}

function ToastRow({ toast, onDismiss }: { toast: Toast; onDismiss: () => void }) {
  useEffect(() => {
    const timer = setTimeout(onDismiss, DISMISS_AFTER_MS);
    return () => clearTimeout(timer);
  }, [onDismiss]);

  const success = toast.tone === "success";
  return (
    <div
      className={cn(
        "pointer-events-auto flex w-full max-w-sm items-start gap-2.5 rounded-xl border px-3.5 py-3 text-[13px] shadow-lg backdrop-blur motion-safe:animate-fade-up",
        success
          ? "border-signal/30 bg-ink/95 text-fg"
          : "border-danger/40 bg-ink/95 text-fg"
      )}
    >
      <span className={cn("mt-0.5 shrink-0", success ? "text-signal" : "text-danger")}>
        {success ? (
          <Check className="h-4 w-4" strokeWidth={2.5} />
        ) : (
          <AlertTriangle className="h-4 w-4" strokeWidth={2} />
        )}
      </span>
      <p className="min-w-0 flex-1 leading-relaxed">{toast.message}</p>
      <button
        type="button"
        onClick={onDismiss}
        aria-label="Dismiss"
        className="-m-1 shrink-0 rounded p-1 text-faint transition-colors hover:text-fg"
      >
        <X className="h-3.5 w-3.5" strokeWidth={2} />
      </button>
    </div>
  );
}

export function useToast(): ToastApi {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error("useToast must be used inside <ToastProvider>");
  return ctx;
}
