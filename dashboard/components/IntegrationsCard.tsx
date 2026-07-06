"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Bell, Check, KeyRound, Loader2 } from "lucide-react";
import { useState } from "react";

import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { Button, Card, Pill } from "@/components/ui";

const inputCls =
  "w-full rounded-lg border border-line bg-ink px-3 py-2.5 text-[13px] text-fg placeholder:text-faint focus:border-cyan/60";

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div>
      <label className="mb-1.5 block font-mono text-[11px] uppercase tracking-wide text-faint">
        {label}
        {hint ? <span className="text-faint/70"> ({hint})</span> : null}
      </label>
      {children}
    </div>
  );
}

export function IntegrationsCard() {
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const [llmModel, setLlmModel] = useState(user?.llm_model ?? "");
  const [llmKey, setLlmKey] = useState("");
  const [slack, setSlack] = useState("");

  const canByok =
    user?.subscription_tier === "pro" || user?.subscription_tier === "enterprise";

  const save = useMutation({
    mutationFn: (body: {
      llm_model?: string | null;
      llm_api_key?: string | null;
      slack_webhook_url?: string | null;
    }) => api.updateIntegrations(body),
    onSuccess: () => {
      setLlmKey("");
      setSlack("");
      queryClient.invalidateQueries({ queryKey: ["me"] });
    },
  });

  if (!user) return null;

  const error = save.error instanceof ApiError ? save.error.message : null;

  const onSave = () => {
    const body: Record<string, string> = {};
    if (canByok) body.llm_model = llmModel.trim();
    if (llmKey.trim()) body.llm_api_key = llmKey.trim();
    if (slack.trim()) body.slack_webhook_url = slack.trim();
    save.mutate(body);
  };

  return (
    <Card className="mt-5 p-5">
      <div className="mb-4 flex items-center gap-2.5">
        <span className="grid h-9 w-9 place-items-center rounded-lg border border-line bg-ink text-fg">
          <KeyRound className="h-4 w-4" strokeWidth={1.75} />
        </span>
        <div>
          <h2 className="font-display text-[15px] font-semibold text-fg">Integrations</h2>
          <p className="text-[12px] text-muted">
            Bring your own LLM key and get Slack notifications when scans finish.
          </p>
        </div>
      </div>

      <div className="space-y-3.5">
        <Field label="LLM model" hint="Pro & above">
          <input
            type="text"
            placeholder="anthropic/claude-sonnet-4-6"
            value={llmModel}
            disabled={!canByok}
            onChange={(e) => setLlmModel(e.target.value)}
            className={`${inputCls} disabled:opacity-50`}
          />
        </Field>
        <Field label="LLM API key" hint={canByok ? "write-only" : "Pro & above"}>
          <div className="flex items-center gap-2">
            <input
              type="password"
              autoComplete="new-password"
              placeholder={user.has_llm_key ? "•••••• (set)" : "sk-…"}
              value={llmKey}
              disabled={!canByok}
              onChange={(e) => setLlmKey(e.target.value)}
              className={`${inputCls} disabled:opacity-50`}
            />
            {user.has_llm_key ? (
              <Pill tone="border-signal/30 bg-signal/10 text-signal">Set</Pill>
            ) : null}
          </div>
        </Field>

        {!canByok ? (
          <p className="rounded-lg border border-amber/30 bg-amber/[0.06] px-3 py-2.5 text-[12px] leading-relaxed text-amber">
            Bring-your-own-key is available on the Pro plan and above.
          </p>
        ) : null}

        <div className="border-t border-line pt-3.5">
          <Field label="Slack webhook URL" hint="optional">
            <div className="flex items-center gap-2">
              <input
                type="url"
                placeholder={
                  user.has_slack
                    ? "•••••• (set)"
                    : "https://hooks.slack.com/services/…"
                }
                value={slack}
                onChange={(e) => setSlack(e.target.value)}
                className={inputCls}
              />
              {user.has_slack ? (
                <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full border border-signal/30 bg-signal/10 text-signal">
                  <Bell className="h-4 w-4" strokeWidth={2} />
                </span>
              ) : null}
            </div>
          </Field>
        </div>

        {error ? <p className="text-[12px] text-danger">{error}</p> : null}
        {save.isSuccess && !save.isPending ? (
          <p className="flex items-center gap-1.5 text-[12px] text-signal">
            <Check className="h-3.5 w-3.5" strokeWidth={2.5} /> Saved.
          </p>
        ) : null}

        <Button onClick={onSave} disabled={save.isPending}>
          {save.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" strokeWidth={2} />
          ) : null}
          Save integrations
        </Button>
      </div>
    </Card>
  );
}
