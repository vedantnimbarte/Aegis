"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Check,
  Github,
  Loader2,
  Plug,
  Trash2,
  ExternalLink,
} from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef } from "react";

import { api, ApiError } from "@/lib/api";
import { Button, Card, ErrorState, PageHeader, Pill, Spinner } from "@/components/ui";
import { relativeTime } from "@/lib/format";
import type { Installation } from "@/lib/types";

function SettingsInner() {
  const router = useRouter();
  const params = useSearchParams();
  const queryClient = useQueryClient();
  const claimed = useRef(false);

  const appQuery = useQuery({ queryKey: ["github-app"], queryFn: api.getGitHubApp });

  const claim = useMutation({
    mutationFn: (installationId: string) => api.claimInstallation(installationId),
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["github-app"] });
      // Drop the query params so a refresh doesn't re-claim.
      router.replace("/settings");
    },
  });

  // Handle the post-install redirect: ?installation_id=…&setup_action=install
  useEffect(() => {
    if (claimed.current) return;
    const installationId = params.get("installation_id");
    if (installationId) {
      claimed.current = true;
      claim.mutate(installationId);
    }
  }, [params, claim]);

  const disconnect = useMutation({
    mutationFn: (id: string) => api.deleteInstallation(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["github-app"] }),
  });

  if (appQuery.isLoading) return <Spinner label="Loading settings…" />;
  if (appQuery.error || !appQuery.data)
    return <ErrorState message="Could not load settings." />;

  const app = appQuery.data;
  const claimError = claim.error instanceof ApiError ? claim.error.message : null;

  return (
    <>
      <PageHeader title="Settings" subtitle="Integrations and account configuration." />

      <Card className="p-5">
        <div className="mb-4 flex items-center gap-2.5">
          <span className="grid h-9 w-9 place-items-center rounded-lg border border-line bg-ink text-fg">
            <Github className="h-4 w-4" strokeWidth={1.75} />
          </span>
          <div>
            <h2 className="font-display text-[15px] font-semibold text-fg">GitHub App</h2>
            <p className="text-[12px] text-muted">
              Scan pull requests automatically and post findings before merge.
            </p>
          </div>
        </div>

        {!app.configured ? (
          <p className="rounded-lg border border-amber/30 bg-amber/[0.06] px-3 py-2.5 text-[12px] leading-relaxed text-amber">
            The GitHub App isn&rsquo;t configured on the server yet. Set the
            GITHUB_APP_* environment variables to enable PR scanning.
          </p>
        ) : (
          <>
            {claim.isPending ? (
              <div className="mb-3 flex items-center gap-2 text-[13px] text-muted">
                <Loader2 className="h-4 w-4 animate-spin" strokeWidth={2} />
                Linking your installation…
              </div>
            ) : null}
            {claimError ? (
              <div className="mb-3">
                <ErrorState message={claimError} />
              </div>
            ) : null}

            {app.installations.length === 0 ? (
              <p className="mb-4 text-[13px] leading-relaxed text-muted">
                No installations linked yet. Install the Aegis GitHub App on the
                repositories or organization you want scanned on every pull request.
              </p>
            ) : (
              <ul className="mb-4 divide-y divide-line overflow-hidden rounded-lg border border-line">
                {app.installations.map((inst) => (
                  <InstallationRow
                    key={inst.id}
                    installation={inst}
                    disconnecting={disconnect.isPending && disconnect.variables === inst.id}
                    onDisconnect={() => disconnect.mutate(inst.id)}
                  />
                ))}
              </ul>
            )}

            <a
              href={app.install_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center justify-center gap-2 rounded-lg bg-cyan px-4 py-2.5 font-display text-[13px] font-semibold text-obsidian transition-all hover:bg-cyan-soft"
            >
              <Plug className="h-4 w-4" strokeWidth={2} />
              {app.installations.length === 0 ? "Install the GitHub App" : "Add another installation"}
              <ExternalLink className="h-3.5 w-3.5" strokeWidth={2} />
            </a>
          </>
        )}
      </Card>
    </>
  );
}

function InstallationRow({
  installation,
  disconnecting,
  onDisconnect,
}: {
  installation: Installation;
  disconnecting: boolean;
  onDisconnect: () => void;
}) {
  return (
    <li className="flex items-center gap-3 bg-surface/40 px-4 py-3">
      <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full border border-signal/30 bg-signal/10 text-signal">
        <Check className="h-4 w-4" strokeWidth={2.5} />
      </span>
      <div className="min-w-0 flex-1">
        <p className="truncate font-mono text-[13px] text-fg">{installation.account_login}</p>
        <p className="text-[11px] text-faint">Linked {relativeTime(installation.created_at)}</p>
      </div>
      <Pill tone="border-signal/30 bg-signal/10 text-signal">Active</Pill>
      <Button
        variant="ghost"
        icon={Trash2}
        loading={disconnecting}
        onClick={onDisconnect}
        aria-label="Disconnect installation"
      >
        Disconnect
      </Button>
    </li>
  );
}

export default function SettingsPage() {
  return (
    <Suspense fallback={<Spinner label="Loading settings…" />}>
      <SettingsInner />
    </Suspense>
  );
}
