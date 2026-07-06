"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { GitBranch, Lock, Plus, Radar, Check, ExternalLink } from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { NewScanDialog } from "@/components/NewScanDialog";
import {
  Button,
  Card,
  EmptyState,
  ErrorState,
  PageHeader,
  Spinner,
} from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { relativeTime } from "@/lib/format";
import type { GitHubRepo, Repository } from "@/lib/types";

export default function ReposPage() {
  const queryClient = useQueryClient();
  const [scanRepoId, setScanRepoId] = useState<string | null>(null);

  const connectedQuery = useQuery({ queryKey: ["repos"], queryFn: api.listRepos });
  const availableQuery = useQuery({
    queryKey: ["repos", "available"],
    queryFn: api.listAvailableRepos,
    retry: false,
  });

  const connected = connectedQuery.data ?? [];
  const connectedKeys = useMemo(
    () => new Set(connected.map((r) => r.github_repo_id)),
    [connected]
  );

  const connectMutation = useMutation({
    mutationFn: (repo: GitHubRepo) =>
      api.syncRepo({ github_repo_id: repo.github_repo_id, name: repo.name, url: repo.url }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["repos"] }),
  });

  if (connectedQuery.isLoading) return <Spinner label="Loading repositories…" />;

  const available = (availableQuery.data ?? []).filter((r) => !connectedKeys.has(r.github_repo_id));

  return (
    <>
      <PageHeader
        title="Repositories"
        subtitle="Connect GitHub repositories and launch pentests against them."
      />

      {/* Connected */}
      <section>
        <h2 className="mb-4 font-display text-[15px] font-semibold text-fg">Connected</h2>
        {connected.length === 0 ? (
          <EmptyState icon={GitBranch} title="No repositories connected">
            Connect one of your GitHub repositories below to start scanning.
          </EmptyState>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {connected.map((repo) => (
              <ConnectedCard key={repo.id} repo={repo} onScan={() => setScanRepoId(repo.id)} />
            ))}
          </div>
        )}
      </section>

      {/* Available from GitHub */}
      <section className="mt-10">
        <h2 className="mb-4 font-display text-[15px] font-semibold text-fg">Available on GitHub</h2>

        {availableQuery.isLoading ? (
          <Spinner label="Fetching your GitHub repositories…" />
        ) : availableQuery.error ? (
          <ErrorState message="Couldn't load your GitHub repositories. Reconnect your GitHub account or check the token scope." />
        ) : available.length === 0 ? (
          <EmptyState icon={Check} title="All caught up">
            Every repository we can see from your GitHub account is already connected.
          </EmptyState>
        ) : (
          <Card>
            <ul className="divide-y divide-line">
              {available.map((repo) => (
                <AvailableRow
                  key={repo.github_repo_id}
                  repo={repo}
                  connecting={
                    connectMutation.isPending &&
                    connectMutation.variables?.github_repo_id === repo.github_repo_id
                  }
                  onConnect={() => connectMutation.mutate(repo)}
                />
              ))}
            </ul>
          </Card>
        )}

        {connectMutation.error ? (
          <div className="mt-3 space-y-2.5">
            <ErrorState
              message={
                connectMutation.error instanceof ApiError
                  ? connectMutation.error.message
                  : "Could not connect that repository. Please try again."
              }
            />
            {connectMutation.error instanceof ApiError &&
            connectMutation.error.status === 402 ? (
              <Link
                href="/billing"
                className="inline-flex items-center gap-1.5 text-[12px] font-medium text-cyan-soft hover:text-cyan"
              >
                View plans &amp; upgrade →
              </Link>
            ) : null}
          </div>
        ) : null}
      </section>

      {scanRepoId ? (
        <NewScanDialog
          repositories={connected}
          defaultRepoId={scanRepoId}
          onClose={() => setScanRepoId(null)}
        />
      ) : null}
    </>
  );
}

function ConnectedCard({ repo, onScan }: { repo: Repository; onScan: () => void }) {
  return (
    <Card className="flex flex-col gap-3 p-4">
      <div className="flex items-start gap-3">
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-line bg-ink text-cyan-soft">
          <GitBranch className="h-4 w-4" strokeWidth={1.75} />
        </span>
        <div className="min-w-0 flex-1">
          <a
            href={repo.url}
            target="_blank"
            rel="noopener noreferrer"
            className="group inline-flex items-center gap-1.5 font-mono text-[13px] text-fg hover:text-cyan-soft"
          >
            <span className="truncate">{repo.name}</span>
            <ExternalLink className="h-3 w-3 shrink-0 opacity-0 transition-opacity group-hover:opacity-100" />
          </a>
          <p className="mt-0.5 text-[11px] text-faint">Connected {relativeTime(repo.created_at)}</p>
        </div>
      </div>
      <Button variant="secondary" icon={Radar} className="w-full" onClick={onScan}>
        New scan
      </Button>
    </Card>
  );
}

function AvailableRow({
  repo,
  connecting,
  onConnect,
}: {
  repo: GitHubRepo;
  connecting: boolean;
  onConnect: () => void;
}) {
  return (
    <li className="flex items-center gap-3 px-4 py-3">
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="truncate font-mono text-[13px] text-fg">{repo.name}</span>
          {repo.private ? (
            <Lock className="h-3 w-3 shrink-0 text-faint" strokeWidth={2} />
          ) : null}
        </div>
        {repo.description ? (
          <p className="mt-0.5 truncate text-[11px] text-muted">{repo.description}</p>
        ) : null}
      </div>
      <Button variant="secondary" icon={Plus} loading={connecting} onClick={onConnect}>
        Connect
      </Button>
    </li>
  );
}
