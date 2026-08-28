"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bot,
  CalendarClock,
  Check,
  Crosshair,
  ExternalLink,
  Globe,
  GitBranch,
  KeyRound,
  Lock,
  Plug,
  Plus,
  Radar,
  Settings2,
  Sparkles,
} from "lucide-react";
import Link from "next/link";
import { useMemo, useState } from "react";

import { AddTargetDialog } from "@/components/AddTargetDialog";
import { GreyboxDialog } from "@/components/GreyboxDialog";
import { NewScanDialog } from "@/components/NewScanDialog";
import { ScheduleDialog } from "@/components/ScheduleDialog";
import { TargetSettingsDialog } from "@/components/TargetSettingsDialog";
import { useToast } from "@/components/Toast";
import {
  Button,
  Card,
  EmptyState,
  ErrorState,
  PageHeader,
  SeverityCountList,
  Skeleton,
  SkeletonList,
  StatusBadge,
} from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { formatDate, relativeTime } from "@/lib/format";
import type {
  GitProvider,
  Scan,
  Schedule,
  SourceRepo,
  Target,
  TargetKind,
} from "@/lib/types";

const KIND_ICON: Record<TargetKind, typeof Globe> = {
  repo: GitBranch,
  web: Globe,
  api: Plug,
  llm: Sparkles,
  mcp: Bot,
};

const KIND_LABEL: Record<TargetKind, string> = {
  repo: "Repository",
  web: "Web app",
  api: "API",
  llm: "LLM app",
  mcp: "MCP server",
};

const PROVIDERS: { value: GitProvider; label: string }[] = [
  { value: "github", label: "GitHub" },
  { value: "gitlab", label: "GitLab" },
  { value: "bitbucket", label: "Bitbucket" },
];

export default function TargetsPage() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [scanTargetId, setScanTargetId] = useState<string | null>(null);
  const [scheduleFor, setScheduleFor] = useState<{
    target: Target;
    existing: Schedule | null;
  } | null>(null);
  const [greyboxFor, setGreyboxFor] = useState<Target | null>(null);
  const [settingsFor, setSettingsFor] = useState<Target | null>(null);
  const [adding, setAdding] = useState(false);
  const [provider, setProvider] = useState<GitProvider>("github");

  const connectedQuery = useQuery({
    queryKey: ["targets"],
    queryFn: () => api.listTargets(),
  });
  const availableQuery = useQuery({
    queryKey: ["targets", "available", provider],
    queryFn: () => api.listAvailableRepos(provider),
    retry: false,
  });
  const schedulesQuery = useQuery({
    queryKey: ["schedules"],
    queryFn: () => api.listSchedules(),
  });
  const scansQuery = useQuery({ queryKey: ["scans"], queryFn: () => api.listScans() });

  const connected = connectedQuery.data ?? [];
  const connectedKeys = useMemo(
    () => new Set(connected.map((t) => t.external_repo_id).filter(Boolean)),
    [connected]
  );
  const scheduleByTarget = useMemo(
    () => new Map((schedulesQuery.data ?? []).map((s) => [s.target_id, s])),
    [schedulesQuery.data]
  );
  // Scans arrive newest first, so the first hit per target is the latest one.
  const latestScanByTarget = useMemo(() => {
    const map = new Map<string, Scan>();
    for (const scan of scansQuery.data ?? []) {
      if (!map.has(scan.target_id)) map.set(scan.target_id, scan);
    }
    return map;
  }, [scansQuery.data]);

  const connectMutation = useMutation({
    mutationFn: (repo: SourceRepo) =>
      api.connectRepo({
        provider: repo.provider,
        external_repo_id: repo.external_repo_id,
        name: repo.name,
        clone_url: repo.clone_url,
      }),
    onSuccess: (_data, repo) => {
      queryClient.invalidateQueries({ queryKey: ["targets"] });
      toast.success(`Connected ${repo.name}.`);
    },
    onError: (err) => toast.fromError(err, "Could not connect that repository."),
  });

  const available = (availableQuery.data ?? []).filter(
    (r) => !connectedKeys.has(r.external_repo_id)
  );

  return (
    <>
      <PageHeader
        title="Targets"
        subtitle="Everything Aegis tests — repositories, running apps, APIs, and AI endpoints."
        action={
          <Button icon={Plus} onClick={() => setAdding(true)}>
            Add target
          </Button>
        }
      />

      {/* Connected */}
      <section>
        <h2 className="mb-4 font-display text-[15px] font-semibold text-fg">Connected</h2>
        {connectedQuery.isLoading ? (
          <div className="grid gap-3 sm:grid-cols-2">
            {Array.from({ length: 2 }, (_, i) => (
              <Card key={i} className="space-y-3 p-4">
                <Skeleton className="h-4 w-1/2" />
                <Skeleton className="h-2.5 w-1/3" />
                <Skeleton className="h-9 w-full rounded-lg" />
              </Card>
            ))}
          </div>
        ) : connected.length === 0 ? (
          <EmptyState
            icon={Crosshair}
            title="No targets yet"
            action={
              <Button icon={Plus} onClick={() => setAdding(true)}>
                Add a target
              </Button>
            }
          >
            Add a running app, an API, or an AI endpoint by URL — or connect a
            repository from a source host below.
          </EmptyState>
        ) : (
          <div className="grid gap-3 sm:grid-cols-2">
            {connected.map((target) => (
              <TargetCard
                key={target.id}
                target={target}
                schedule={scheduleByTarget.get(target.id) ?? null}
                lastScan={latestScanByTarget.get(target.id) ?? null}
                onScan={() => setScanTargetId(target.id)}
                onSchedule={() =>
                  setScheduleFor({
                    target,
                    existing: scheduleByTarget.get(target.id) ?? null,
                  })
                }
                onGreybox={() => setGreyboxFor(target)}
                onSettings={() => setSettingsFor(target)}
              />
            ))}
          </div>
        )}
      </section>

      {/* Available from a source host */}
      <section className="mt-10">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <h2 className="font-display text-[15px] font-semibold text-fg">
            Repositories you can connect
          </h2>
          <div className="flex gap-1.5">
            {PROVIDERS.map((p) => (
              <button
                key={p.value}
                type="button"
                onClick={() => setProvider(p.value)}
                className={
                  "rounded-lg border px-3 py-1.5 text-[12px] font-medium transition-colors " +
                  (provider === p.value
                    ? "border-cyan/50 bg-cyan/10 text-cyan-soft"
                    : "border-line bg-ink text-faint hover:border-line/80")
                }
              >
                {p.label}
              </button>
            ))}
          </div>
        </div>

        {availableQuery.isLoading ? (
          <SkeletonList rows={4} />
        ) : availableQuery.error ? (
          <ErrorState
            message={
              availableQuery.error instanceof ApiError
                ? availableQuery.error.message
                : `Could not load your ${provider} repositories. Add a token for this host in Settings.`
            }
          />
        ) : available.length === 0 ? (
          <EmptyState icon={Check} title="All caught up">
            Every repository we can see on {provider} is already connected.
          </EmptyState>
        ) : (
          <Card>
            <ul className="divide-y divide-line">
              {available.map((repo) => (
                <AvailableRow
                  key={repo.external_repo_id}
                  repo={repo}
                  connecting={
                    connectMutation.isPending &&
                    connectMutation.variables?.external_repo_id === repo.external_repo_id
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

      {adding ? <AddTargetDialog onClose={() => setAdding(false)} /> : null}

      {scanTargetId ? (
        <NewScanDialog
          targets={connected}
          defaultTargetId={scanTargetId}
          onClose={() => setScanTargetId(null)}
        />
      ) : null}

      {scheduleFor ? (
        <ScheduleDialog
          target={scheduleFor.target}
          existing={scheduleFor.existing}
          onClose={() => setScheduleFor(null)}
        />
      ) : null}

      {greyboxFor ? (
        <GreyboxDialog target={greyboxFor} onClose={() => setGreyboxFor(null)} />
      ) : null}

      {settingsFor ? (
        <TargetSettingsDialog
          target={settingsFor}
          onClose={() => setSettingsFor(null)}
        />
      ) : null}
    </>
  );
}

function TargetCard({
  target,
  schedule,
  lastScan,
  onScan,
  onSchedule,
  onGreybox,
  onSettings,
}: {
  target: Target;
  schedule: Schedule | null;
  lastScan: Scan | null;
  onScan: () => void;
  onSchedule: () => void;
  onGreybox: () => void;
  onSettings: () => void;
}) {
  const Icon = KIND_ICON[target.kind] ?? Globe;
  const href = target.url ?? target.clone_url ?? undefined;

  return (
    <Card className="flex flex-col gap-3 p-4">
      <div className="flex items-start gap-3">
        <span className="grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-line bg-ink text-cyan-soft">
          <Icon className="h-4 w-4" strokeWidth={1.75} />
        </span>
        <div className="min-w-0 flex-1">
          {href ? (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="group inline-flex items-center gap-1.5 font-mono text-[13px] text-fg hover:text-cyan-soft"
            >
              <span className="truncate">{target.name}</span>
              <ExternalLink className="h-3 w-3 shrink-0 opacity-0 transition-opacity group-hover:opacity-100" />
            </a>
          ) : (
            <span className="truncate font-mono text-[13px] text-fg">{target.name}</span>
          )}
          <p className="mt-0.5 text-[11px] text-faint">
            {KIND_LABEL[target.kind]}
            {target.provider ? ` · ${target.provider}` : ""} · added{" "}
            {relativeTime(target.created_at)}
          </p>
        </div>
        <button
          onClick={onSettings}
          aria-label="Target settings"
          className="grid h-8 w-8 shrink-0 place-items-center rounded-lg text-faint hover:bg-ink hover:text-fg"
        >
          <Settings2 className="h-4 w-4" strokeWidth={1.75} />
        </button>
      </div>

      {/* The target's current health — the reason it is connected at all, and
          previously only visible by leaving this page. */}
      {lastScan ? (
        <Link
          href={`/scans/${lastScan.id}`}
          className="flex items-center gap-2 rounded-lg border border-line bg-ink px-3 py-2 transition-colors hover:border-cyan/30"
        >
          <div className="min-w-0 flex-1">
            {lastScan.counts_by_severity ? (
              <SeverityCountList
                counts={lastScan.counts_by_severity}
                emptyLabel="No findings"
              />
            ) : (
              <span className="font-mono text-[11px] text-faint">No results yet</span>
            )}
            <p className="mt-0.5 text-[11px] text-faint">
              Last scan {relativeTime(lastScan.created_at)}
            </p>
          </div>
          <StatusBadge status={lastScan.status} />
        </Link>
      ) : (
        <p className="rounded-lg border border-dashed border-line px-3 py-2 text-[11px] text-faint">
          Never scanned
        </p>
      )}

      {schedule ? (
        <div className="flex items-center gap-2 rounded-lg border border-line bg-ink px-3 py-2 text-[11px]">
          <CalendarClock className="h-3.5 w-3.5 shrink-0 text-cyan-soft" strokeWidth={2} />
          {schedule.enabled ? (
            <span className="text-muted">
              <span className="capitalize text-fg">{schedule.frequency}</span> {schedule.scan_mode}{" "}
              scan · next {formatDate(schedule.next_run_at)}
            </span>
          ) : (
            <span className="text-faint">Schedule paused</span>
          )}
        </div>
      ) : null}

      <div className="flex flex-wrap gap-1.5 text-[11px]">
        {target.has_greybox ? <Tag icon={KeyRound}>Authenticated</Tag> : null}
        {target.has_derived_spec ? <Tag icon={Plug}>API routes derived</Tag> : null}
        {target.discovery_enabled ? <Tag icon={Radar}>Watching for new hosts</Tag> : null}
        {target.kind === "repo" && !target.url ? (
          <Tag icon={Globe} muted>
            No live URL — cannot verify fixes
          </Tag>
        ) : null}
      </div>

      <Button variant="secondary" icon={Radar} className="w-full" onClick={onScan}>
        New scan
      </Button>
      <div className="flex gap-2">
        <Button
          variant="secondary"
          icon={CalendarClock}
          className="flex-1"
          onClick={onSchedule}
          aria-label={schedule ? "Edit schedule" : "Set up recurring scans"}
        >
          Schedule
        </Button>
        <Button
          variant="secondary"
          icon={KeyRound}
          className="flex-1"
          onClick={onGreybox}
          aria-label={
            target.has_greybox
              ? "Edit authenticated testing"
              : "Set up authenticated testing"
          }
        >
          Auth
        </Button>
      </div>
    </Card>
  );
}

function Tag({
  icon: Icon,
  muted,
  children,
}: {
  icon: typeof Globe;
  muted?: boolean;
  children: React.ReactNode;
}) {
  return (
    <span
      className={
        "inline-flex items-center gap-1.5 rounded-md border px-2 py-1 " +
        (muted
          ? "border-line bg-ink text-faint"
          : "border-line bg-ink text-muted")
      }
    >
      <Icon className="h-3 w-3 shrink-0 text-cyan-soft" strokeWidth={2} />
      {children}
    </span>
  );
}

function AvailableRow({
  repo,
  connecting,
  onConnect,
}: {
  repo: SourceRepo;
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
