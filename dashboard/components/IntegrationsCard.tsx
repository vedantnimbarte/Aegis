"use client";

// Everything Aegis connects out to: the LLM it runs on, where scan results are
// announced, where findings get filed, and the source hosts beyond GitHub.
//
// Every credential here is write-only. Reads return a boolean saying whether
// it is set, never the value, so a compromised session cannot exfiltrate the
// customer's Jira token by loading a settings page.

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Bell, Check, GitBranch, KeyRound, Loader2, Ticket } from "lucide-react";
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

function SectionHeading({
  icon: Icon,
  title,
  blurb,
}: {
  icon: typeof KeyRound;
  title: string;
  blurb: string;
}) {
  return (
    <div className="mb-3 flex items-start gap-2.5">
      <Icon className="mt-0.5 h-4 w-4 shrink-0 text-cyan-soft" strokeWidth={2} />
      <div>
        <h3 className="font-display text-[13px] font-semibold text-fg">{title}</h3>
        <p className="text-[11px] leading-relaxed text-muted">{blurb}</p>
      </div>
    </div>
  );
}

export function IntegrationsCard() {
  const { user } = useAuth();
  const queryClient = useQueryClient();

  const [llmModel, setLlmModel] = useState(user?.llm_model ?? "");
  const [llmKey, setLlmKey] = useState("");
  const [slack, setSlack] = useState("");
  const [gitlab, setGitlab] = useState("");
  const [bitbucket, setBitbucket] = useState("");
  const [jiraUrl, setJiraUrl] = useState(user?.jira_url ?? "");
  const [jiraEmail, setJiraEmail] = useState("");
  const [jiraToken, setJiraToken] = useState("");
  const [jiraProject, setJiraProject] = useState(user?.jira_project_key ?? "");
  const [linearKey, setLinearKey] = useState("");
  const [linearTeam, setLinearTeam] = useState(user?.linear_team_id ?? "");

  const canByok =
    user?.subscription_tier === "pro" || user?.subscription_tier === "enterprise";

  const save = useMutation({
    mutationFn: (body: Record<string, string>) => api.updateIntegrations(body),
    onSuccess: () => {
      // Only the secrets are cleared; the identifiers stay so the form still
      // shows what is configured.
      setLlmKey("");
      setSlack("");
      setGitlab("");
      setBitbucket("");
      setJiraToken("");
      setLinearKey("");
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
    if (gitlab.trim()) body.gitlab_token = gitlab.trim();
    if (bitbucket.trim()) body.bitbucket_token = bitbucket.trim();
    if (jiraUrl.trim()) body.jira_url = jiraUrl.trim();
    if (jiraEmail.trim()) body.jira_email = jiraEmail.trim();
    if (jiraToken.trim()) body.jira_api_token = jiraToken.trim();
    if (jiraProject.trim()) body.jira_project_key = jiraProject.trim();
    if (linearKey.trim()) body.linear_api_key = linearKey.trim();
    if (linearTeam.trim()) body.linear_team_id = linearTeam.trim();
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
            Your own LLM key, where results are announced, and where findings
            get filed.
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

        {/* Notifications */}
        <div className="border-t border-line pt-4">
          <SectionHeading
            icon={Bell}
            title="Notifications"
            blurb="Announced when a scan finishes or new assets are discovered."
          />
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

        {/* Issue trackers */}
        <div className="border-t border-line pt-4">
          <SectionHeading
            icon={Ticket}
            title="Issue tracker"
            blurb="Where a finding is filed. Jira and Linear take precedence over GitHub issues once configured."
          />
          <div className="grid gap-3.5 sm:grid-cols-2">
            <Field label="Jira site URL">
              <input
                type="url"
                placeholder="https://acme.atlassian.net"
                value={jiraUrl}
                onChange={(e) => setJiraUrl(e.target.value)}
                className={inputCls}
              />
            </Field>
            <Field label="Jira project key">
              <input
                type="text"
                placeholder="SEC"
                value={jiraProject}
                onChange={(e) => setJiraProject(e.target.value)}
                className={inputCls}
              />
            </Field>
            <Field label="Jira account email">
              <input
                type="email"
                placeholder="security@acme.com"
                value={jiraEmail}
                onChange={(e) => setJiraEmail(e.target.value)}
                className={inputCls}
              />
            </Field>
            <Field label="Jira API token" hint="write-only">
              <div className="flex items-center gap-2">
                <input
                  type="password"
                  autoComplete="new-password"
                  placeholder={user.has_jira ? "•••••• (set)" : "ATATT…"}
                  value={jiraToken}
                  onChange={(e) => setJiraToken(e.target.value)}
                  className={inputCls}
                />
                {user.has_jira ? (
                  <Pill tone="border-signal/30 bg-signal/10 text-signal">Set</Pill>
                ) : null}
              </div>
            </Field>
            <Field label="Linear API key" hint="write-only">
              <div className="flex items-center gap-2">
                <input
                  type="password"
                  autoComplete="new-password"
                  placeholder={user.has_linear ? "•••••• (set)" : "lin_api_…"}
                  value={linearKey}
                  onChange={(e) => setLinearKey(e.target.value)}
                  className={inputCls}
                />
                {user.has_linear ? (
                  <Pill tone="border-signal/30 bg-signal/10 text-signal">Set</Pill>
                ) : null}
              </div>
            </Field>
            <Field label="Linear team ID">
              <input
                type="text"
                placeholder="a1b2c3d4-…"
                value={linearTeam}
                onChange={(e) => setLinearTeam(e.target.value)}
                className={inputCls}
              />
            </Field>
          </div>
        </div>

        {/* Source hosts */}
        <div className="border-t border-line pt-4">
          <SectionHeading
            icon={GitBranch}
            title="Other source hosts"
            blurb="Personal access tokens for connecting repositories outside GitHub."
          />
          <div className="grid gap-3.5 sm:grid-cols-2">
            <Field label="GitLab token" hint="write-only">
              <input
                type="password"
                autoComplete="new-password"
                placeholder="glpat-…"
                value={gitlab}
                onChange={(e) => setGitlab(e.target.value)}
                className={inputCls}
              />
            </Field>
            <Field label="Bitbucket token" hint="write-only">
              <input
                type="password"
                autoComplete="new-password"
                placeholder="Access token"
                value={bitbucket}
                onChange={(e) => setBitbucket(e.target.value)}
                className={inputCls}
              />
            </Field>
          </div>
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
