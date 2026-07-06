"use client";

// Configure authenticated (grey-box) testing for a repository: a live target
// URL plus test credentials Strix uses to log in and test behind the login
// wall. Secrets are write-only — the form shows whether a password/extra is
// already set and preserves it unless the user types a new value.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { KeyRound, Loader2, Trash2, X } from "lucide-react";
import { useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";
import type { Repository } from "@/lib/types";
import { Button, ErrorState } from "./ui";

export function GreyboxDialog({
  repository,
  onClose,
}: {
  repository: Repository;
  onClose: () => void;
}) {
  const queryClient = useQueryClient();
  const hasConfig = repository.has_greybox;

  // Load the existing config (non-secret fields) to prefill when editing.
  const configQuery = useQuery({
    queryKey: ["greybox", repository.id],
    queryFn: () => api.getGreybox(repository.id),
    enabled: hasConfig,
  });

  const [targetUrl, setTargetUrl] = useState("");
  const [loginUrl, setLoginUrl] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [extra, setExtra] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [prefilled, setPrefilled] = useState(false);

  useEffect(() => {
    if (configQuery.data && !prefilled) {
      setTargetUrl(configQuery.data.target_url);
      setLoginUrl(configQuery.data.login_url ?? "");
      setUsername(configQuery.data.username ?? "");
      setPrefilled(true);
    }
  }, [configQuery.data, prefilled]);

  const refresh = () => {
    queryClient.invalidateQueries({ queryKey: ["repos"] });
    queryClient.invalidateQueries({ queryKey: ["greybox", repository.id] });
  };

  const save = useMutation({
    mutationFn: () => {
      const body: {
        target_url: string;
        login_url: string | null;
        username: string | null;
        password?: string;
        extra?: string;
      } = {
        target_url: targetUrl.trim(),
        login_url: loginUrl.trim() || null,
        username: username.trim() || null,
      };
      // Only send secrets when the user typed one, so blanks preserve existing.
      if (password) body.password = password;
      if (extra) body.extra = extra;
      return api.putGreybox(repository.id, body);
    },
    onSuccess: () => {
      refresh();
      onClose();
    },
  });

  const remove = useMutation({
    mutationFn: () => api.deleteGreybox(repository.id),
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

  function onSubmit() {
    setFormError(null);
    const t = targetUrl.trim();
    if (!/^https?:\/\//.test(t)) {
      setFormError("Enter a valid target URL (http:// or https://).");
      return;
    }
    if (loginUrl.trim() && !/^https?:\/\//.test(loginUrl.trim())) {
      setFormError("Login URL must start with http:// or https://.");
      return;
    }
    save.mutate();
  }

  const apiError =
    save.error instanceof ApiError
      ? save.error.message
      : remove.error instanceof ApiError
        ? remove.error.message
        : save.error || remove.error
          ? "Something went wrong. Please try again."
          : null;
  const error = formError || apiError;

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
              <KeyRound className="h-4 w-4" strokeWidth={2} />
            </span>
            <div>
              <h2 className="font-display text-[15px] font-semibold text-fg">
                Authenticated testing
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

        {hasConfig && configQuery.isLoading ? (
          <div className="flex items-center gap-2 px-5 py-8 text-[13px] text-muted">
            <Loader2 className="h-4 w-4 animate-spin" strokeWidth={2} />
            Loading configuration…
          </div>
        ) : (
          <div className="space-y-3.5 px-5 py-5">
            <p className="text-[12px] leading-relaxed text-muted">
              Strix will log in to the live target and test behind the login wall.
              Credentials are encrypted at rest and never shown again.
            </p>

            <Field label="Target URL" required>
              <input
                type="url"
                placeholder="https://staging.your-app.com"
                value={targetUrl}
                onChange={(e) => setTargetUrl(e.target.value)}
                className={inputCls}
              />
            </Field>
            <Field label="Login URL" hint="optional">
              <input
                type="url"
                placeholder="https://staging.your-app.com/login"
                value={loginUrl}
                onChange={(e) => setLoginUrl(e.target.value)}
                className={inputCls}
              />
            </Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label="Username" hint="optional">
                <input
                  type="text"
                  autoComplete="off"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className={inputCls}
                />
              </Field>
              <Field label="Password" hint="optional">
                <input
                  type="password"
                  autoComplete="new-password"
                  placeholder={configQuery.data?.has_password ? "•••••• (set)" : ""}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className={inputCls}
                />
              </Field>
            </div>
            <Field label="Headers / cookies / token" hint="optional">
              <textarea
                rows={2}
                placeholder={
                  configQuery.data?.has_extra
                    ? "•••••• (set) — type to replace"
                    : "e.g. Cookie: session=…  or  Authorization: Bearer …"
                }
                value={extra}
                onChange={(e) => setExtra(e.target.value)}
                className={`${inputCls} resize-none`}
              />
            </Field>

            {error ? <ErrorState message={error} /> : null}
          </div>
        )}

        <div className="flex items-center justify-between gap-2.5 border-t border-line px-5 py-4">
          {hasConfig ? (
            <Button variant="danger" icon={Trash2} loading={remove.isPending} onClick={() => remove.mutate()}>
              Remove
            </Button>
          ) : (
            <span />
          )}
          <div className="flex items-center gap-2.5">
            <Button variant="ghost" onClick={onClose}>
              Cancel
            </Button>
            <Button icon={KeyRound} loading={save.isPending} onClick={onSubmit}>
              Save
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}

const inputCls =
  "w-full rounded-lg border border-line bg-ink px-3 py-2.5 text-[13px] text-fg placeholder:text-faint focus:border-cyan/60";

function Field({
  label,
  hint,
  required,
  children,
}: {
  label: string;
  hint?: string;
  required?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="mb-1.5 block font-mono text-[11px] uppercase tracking-wide text-faint">
        {label}
        {required ? <span className="text-danger"> *</span> : null}
        {hint ? <span className="text-faint/70"> ({hint})</span> : null}
      </label>
      {children}
    </div>
  );
}
