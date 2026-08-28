"use client";

// Team: who is in this organization, what they can do, the machine tokens CI
// uses, and the record of who changed what.

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Building2,
  History,
  KeyRound,
  Plus,
  ScrollText,
  Trash2,
  Users,
} from "lucide-react";
import { useState } from "react";

import { useToast } from "@/components/Toast";
import {
  Button,
  Card,
  EmptyState,
  ErrorState,
  PageHeader,
  Pill,
  Skeleton,
  SkeletonList,
} from "@/components/ui";
import { api } from "@/lib/api";
import { formatDate, relativeTime } from "@/lib/format";
import { atLeast } from "@/lib/types";
import type { ApiToken, AuditEvent, Member, OrgRole } from "@/lib/types";

const ROLES: { value: OrgRole; label: string; blurb: string }[] = [
  { value: "viewer", label: "Viewer", blurb: "Read reports only" },
  { value: "member", label: "Member", blurb: "Run scans and triage findings" },
  { value: "admin", label: "Admin", blurb: "Manage the team and integrations" },
  { value: "owner", label: "Owner", blurb: "Everything, including billing" },
];

const ROLE_TONE: Record<OrgRole, string> = {
  viewer: "border-line bg-ink text-faint",
  member: "border-line bg-ink text-muted",
  admin: "border-cyan/30 bg-cyan/10 text-cyan-soft",
  owner: "border-signal/30 bg-signal/10 text-signal",
};

export default function TeamPage() {
  const orgQuery = useQuery({ queryKey: ["org"], queryFn: () => api.currentOrg() });
  const role = orgQuery.data?.role ?? null;
  const isAdmin = atLeast(role, "admin");

  return (
    <>
      <PageHeader
        title="Team"
        subtitle={
          orgQuery.data
            ? `${orgQuery.data.name} · you are ${role ?? "a member"}`
            : "Members, machine tokens, and the audit trail."
        }
      />

      {orgQuery.data?.is_client_workspace ? (
        <Card className="mb-6 flex items-start gap-3 px-5 py-4">
          <Building2 className="mt-0.5 h-4 w-4 shrink-0 text-cyan-soft" strokeWidth={2} />
          <p className="text-[13px] leading-relaxed text-muted">
            This is a client workspace. Members of the parent organization can
            operate it, and its usage bills to the parent&apos;s plan.
          </p>
        </Card>
      ) : null}

      <MembersCard canManage={isAdmin} currentRole={role} />
      {isAdmin ? <TokensCard /> : null}
      {isAdmin ? <AuditCard /> : null}

      {!isAdmin ? (
        <Card className="mt-6 px-5 py-4">
          <p className="text-[13px] text-muted">
            Machine tokens and the audit log are visible to admins.
          </p>
        </Card>
      ) : null}
    </>
  );
}

/* -------------------------------------------------------------------------- */
function MembersCard({
  canManage,
  currentRole,
}: {
  canManage: boolean;
  currentRole: OrgRole | null;
}) {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<OrgRole>("member");

  const membersQuery = useQuery({
    queryKey: ["org", "members"],
    queryFn: () => api.listMembers(),
  });

  const add = useMutation({
    mutationFn: () => api.addMember({ email: email.trim(), role }),
    onSuccess: (member) => {
      setEmail("");
      queryClient.invalidateQueries({ queryKey: ["org", "members"] });
      toast.success(`${member.email} added as ${member.role}.`);
    },
    onError: (err) => toast.fromError(err, "Could not add that member."),
  });

  const changeRole = useMutation({
    mutationFn: ({ id, next }: { id: string; next: OrgRole }) =>
      api.updateMemberRole(id, next),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["org", "members"] });
      toast.success("Role updated.");
    },
    onError: (err) => toast.fromError(err, "Could not change that role."),
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.removeMember(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["org", "members"] });
      toast.success("Member removed.");
    },
    onError: (err) => toast.fromError(err, "Could not remove that member."),
  });

  const members = membersQuery.data ?? [];

  return (
    <Card className="mb-6 p-5">
      <div className="mb-4 flex items-center gap-2.5">
        <span className="grid h-9 w-9 place-items-center rounded-lg border border-line bg-ink text-cyan-soft">
          <Users className="h-4 w-4" strokeWidth={1.75} />
        </span>
        <div>
          <h2 className="font-display text-[15px] font-semibold text-fg">Members</h2>
          <p className="text-[12px] text-muted">
            Targets, scans and findings belong to the organization, not to a person.
          </p>
        </div>
      </div>

      {membersQuery.isLoading ? (
        <SkeletonList rows={3} />
      ) : (
        <ul className="mb-4 divide-y divide-line overflow-hidden rounded-lg border border-line">
          {members.map((member) => (
            <MemberRow
              key={member.id}
              member={member}
              canManage={canManage}
              currentRole={currentRole}
              onChangeRole={(next) => changeRole.mutate({ id: member.id, next })}
              onRemove={() => remove.mutate(member.id)}
              removing={remove.isPending && remove.variables === member.id}
            />
          ))}
        </ul>
      )}

      {canManage ? (
        <div className="flex flex-wrap items-end gap-2">
          <div className="min-w-[220px] flex-1">
            <label className="mb-1.5 block font-mono text-[11px] uppercase tracking-wide text-faint">
              Add someone with an Aegis account
            </label>
            <input
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="teammate@company.com"
              className="w-full rounded-lg border border-line bg-ink px-3 py-2.5 text-[13px] text-fg placeholder:text-faint focus:border-cyan/60"
            />
          </div>
          <select
            value={role}
            onChange={(e) => setRole(e.target.value as OrgRole)}
            className="rounded-lg border border-line bg-ink px-3 py-2.5 text-[13px] text-fg focus:border-cyan/60"
          >
            {ROLES.map((r) => (
              <option key={r.value} value={r.value}>
                {r.label}
              </option>
            ))}
          </select>
          <Button
            icon={Plus}
            loading={add.isPending}
            disabled={!email.trim()}
            onClick={() => add.mutate()}
          >
            Add
          </Button>
        </div>
      ) : null}

      <dl className="mt-4 grid gap-1.5 sm:grid-cols-2">
        {ROLES.map((r) => (
          <div key={r.value} className="flex items-baseline gap-2 text-[11px]">
            <dt className="font-mono text-faint">{r.label}</dt>
            <dd className="text-muted">{r.blurb}</dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}

function MemberRow({
  member,
  canManage,
  currentRole,
  onChangeRole,
  onRemove,
  removing,
}: {
  member: Member;
  canManage: boolean;
  currentRole: OrgRole | null;
  onChangeRole: (role: OrgRole) => void;
  onRemove: () => void;
  removing: boolean;
}) {
  // Nobody can hand out a role above their own — otherwise an admin could
  // mint an owner and then be removed by them.
  const assignable = ROLES.filter((r) => atLeast(currentRole, r.value));

  return (
    <li className="flex flex-wrap items-center gap-3 bg-surface/40 px-4 py-3">
      <div className="min-w-0 flex-1">
        <p className="truncate text-[13px] text-fg">{member.email}</p>
        <p className="text-[11px] text-faint">Joined {relativeTime(member.created_at)}</p>
      </div>
      {canManage && assignable.length > 1 ? (
        <select
          value={member.role}
          onChange={(e) => onChangeRole(e.target.value as OrgRole)}
          className="rounded-lg border border-line bg-ink px-2.5 py-1.5 font-mono text-[11px] text-fg focus:border-cyan/60"
        >
          {assignable.map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
            </option>
          ))}
        </select>
      ) : (
        <Pill tone={ROLE_TONE[member.role]}>{member.role}</Pill>
      )}
      {canManage ? (
        <Button
          variant="ghost"
          icon={Trash2}
          loading={removing}
          onClick={onRemove}
          aria-label={`Remove ${member.email}`}
        >
          Remove
        </Button>
      ) : null}
    </li>
  );
}

/* -------------------------------------------------------------------------- */
function TokensCard() {
  const queryClient = useQueryClient();
  const toast = useToast();
  const [name, setName] = useState("");
  const [role, setRole] = useState<OrgRole>("member");
  const [minted, setMinted] = useState<string | null>(null);

  const tokensQuery = useQuery({
    queryKey: ["org", "tokens"],
    queryFn: () => api.listApiTokens(),
  });

  const create = useMutation({
    mutationFn: () => api.createApiToken({ name: name.trim(), role }),
    onSuccess: (token) => {
      setMinted(token.token);
      setName("");
      queryClient.invalidateQueries({ queryKey: ["org", "tokens"] });
      toast.success("Token created — copy it now.");
    },
    onError: (err) => toast.fromError(err, "Could not create that token."),
  });

  const revoke = useMutation({
    mutationFn: (id: string) => api.revokeApiToken(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["org", "tokens"] });
      toast.success("Token revoked.");
    },
    onError: (err) => toast.fromError(err, "Could not revoke that token."),
  });

  const tokens = tokensQuery.data ?? [];

  return (
    <Card className="mb-6 p-5">
      <div className="mb-4 flex items-center gap-2.5">
        <span className="grid h-9 w-9 place-items-center rounded-lg border border-line bg-ink text-cyan-soft">
          <KeyRound className="h-4 w-4" strokeWidth={1.75} />
        </span>
        <div>
          <h2 className="font-display text-[15px] font-semibold text-fg">API tokens</h2>
          <p className="text-[12px] text-muted">
            For CI and scripts. A token acts as the organization with the role
            you give it.
          </p>
        </div>
      </div>

      {minted ? (
        <div className="mb-4 rounded-lg border border-signal/30 bg-signal/[0.07] px-3 py-2.5">
          <p className="mb-1.5 font-mono text-[10px] uppercase tracking-wide text-signal">
            Copy this now — it is never shown again
          </p>
          <p className="break-all font-mono text-[12px] text-fg">{minted}</p>
        </div>
      ) : null}

      {tokensQuery.isLoading ? (
        <SkeletonList rows={2} />
      ) : tokens.length === 0 ? (
        <p className="mb-4 rounded-lg border border-dashed border-line px-3 py-2.5 text-[12px] text-faint">
          No tokens yet.
        </p>
      ) : (
        <ul className="mb-4 divide-y divide-line overflow-hidden rounded-lg border border-line">
          {tokens.map((token) => (
            <TokenRow
              key={token.id}
              token={token}
              revoking={revoke.isPending && revoke.variables === token.id}
              onRevoke={() => revoke.mutate(token.id)}
            />
          ))}
        </ul>
      )}

      <div className="flex flex-wrap items-end gap-2">
        <div className="min-w-[220px] flex-1">
          <label className="mb-1.5 block font-mono text-[11px] uppercase tracking-wide text-faint">
            Token name
          </label>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="CI — deploy pipeline"
            className="w-full rounded-lg border border-line bg-ink px-3 py-2.5 text-[13px] text-fg placeholder:text-faint focus:border-cyan/60"
          />
        </div>
        <select
          value={role}
          onChange={(e) => setRole(e.target.value as OrgRole)}
          className="rounded-lg border border-line bg-ink px-3 py-2.5 text-[13px] text-fg focus:border-cyan/60"
        >
          {ROLES.filter((r) => r.value !== "owner").map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
            </option>
          ))}
        </select>
        <Button
          icon={Plus}
          loading={create.isPending}
          disabled={!name.trim()}
          onClick={() => create.mutate()}
        >
          Create token
        </Button>
      </div>

      <p className="mt-3 text-[11px] leading-relaxed text-faint">
        Send it as <span className="font-mono text-muted">Authorization: Bearer</span>{" "}
        with the API base URL. Add{" "}
        <span className="font-mono text-muted">X-Aegis-Org</span> only if the
        token should act in a different organization.
      </p>
    </Card>
  );
}

function TokenRow({
  token,
  revoking,
  onRevoke,
}: {
  token: ApiToken;
  revoking: boolean;
  onRevoke: () => void;
}) {
  return (
    <li className="flex flex-wrap items-center gap-3 bg-surface/40 px-4 py-3">
      <div className="min-w-0 flex-1">
        <p className="truncate text-[13px] text-fg">{token.name}</p>
        <p className="font-mono text-[11px] text-faint">
          {token.token_prefix}… ·{" "}
          {token.last_used_at
            ? `last used ${relativeTime(token.last_used_at)}`
            : "never used"}
          {token.expires_at ? ` · expires ${formatDate(token.expires_at)}` : ""}
        </p>
      </div>
      <Pill tone={ROLE_TONE[token.role]}>{token.role}</Pill>
      <Button
        variant="ghost"
        icon={Trash2}
        loading={revoking}
        onClick={onRevoke}
        aria-label={`Revoke ${token.name}`}
      >
        Revoke
      </Button>
    </li>
  );
}

/* -------------------------------------------------------------------------- */
const ACTION_LABEL: Record<string, string> = {
  "target.created": "added a target",
  "target.updated": "updated a target",
  "target.deleted": "deleted a target",
  "target.discovered": "discovered a new asset",
  "scan.created": "launched a scan",
  "scan.canceled": "canceled a scan",
  "finding.retest_requested": "requested a retest",
  "finding.triaged": "triaged a finding",
  "finding.filed": "filed a finding",
  "autofix.pr_opened": "opened a fix pull request",
  "greybox.updated": "changed authenticated-testing credentials",
  "member.added": "added a member",
  "member.role_changed": "changed a member's role",
  "member.removed": "removed a member",
  "token.created": "created an API token",
  "token.revoked": "revoked an API token",
  "share.created": "created a share link",
  "share.revoked": "revoked a share link",
  "share.viewed": "— a share link was viewed",
  "integration.updated": "changed integration settings",
  "org.created": "created the organization",
};

function AuditCard() {
  const eventsQuery = useQuery({
    queryKey: ["org", "audit"],
    queryFn: () => api.listAuditEvents(100),
  });

  const events = eventsQuery.data ?? [];

  return (
    <Card className="p-5">
      <div className="mb-4 flex items-center gap-2.5">
        <span className="grid h-9 w-9 place-items-center rounded-lg border border-line bg-ink text-cyan-soft">
          <ScrollText className="h-4 w-4" strokeWidth={1.75} />
        </span>
        <div>
          <h2 className="font-display text-[15px] font-semibold text-fg">Audit log</h2>
          <p className="text-[12px] text-muted">
            Append-only. Credentials are never recorded — only which setting
            changed.
          </p>
        </div>
      </div>

      {eventsQuery.isLoading ? (
        <div className="space-y-2">
          {Array.from({ length: 4 }, (_, i) => (
            <Skeleton key={i} className="h-8 w-full rounded-lg" />
          ))}
        </div>
      ) : eventsQuery.error ? (
        <ErrorState message="Could not load the audit log." />
      ) : events.length === 0 ? (
        <EmptyState icon={History} title="Nothing recorded yet">
          Actions taken in this organization will appear here.
        </EmptyState>
      ) : (
        <ul className="divide-y divide-line overflow-hidden rounded-lg border border-line">
          {events.map((event) => (
            <AuditRow key={event.id} event={event} />
          ))}
        </ul>
      )}
    </Card>
  );
}

function AuditRow({ event }: { event: AuditEvent }) {
  const label = ACTION_LABEL[event.action] ?? event.action;
  const detail = event.detail ?? {};
  const subject =
    (detail.name as string) ??
    (detail.email as string) ??
    (detail.title as string) ??
    null;

  return (
    <li className="flex flex-wrap items-baseline gap-x-2 gap-y-1 bg-surface/40 px-4 py-2.5 text-[12px]">
      <span className="text-fg">{event.actor_email ?? "Aegis"}</span>
      <span className="text-muted">{label}</span>
      {subject ? <span className="font-mono text-muted">{subject}</span> : null}
      <span className="ml-auto shrink-0 font-mono text-[11px] text-faint">
        {relativeTime(event.created_at)}
      </span>
    </li>
  );
}
