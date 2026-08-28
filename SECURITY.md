# Security Model

This document covers how Aegis isolates the untrusted code it runs and the
residual risks operators must account for. See `specs.md` §5 for the broader
authentication/tenant-isolation requirements.

## The threat: Aegis runs untrusted code

A scan checks out a customer's repository and hands it to the Strix engine,
which **executes it** and spawns its own Docker sandbox containers to perform
dynamic analysis. That target code is untrusted. The primary risk is a
container breakout that reaches the host, the database, or other tenants.

## Isolation: dedicated Docker daemon (dind)

The Celery worker does **not** mount the host Docker socket. Instead it points
`DOCKER_HOST` at a separate, dedicated Docker-in-Docker daemon (the `dind`
service). Strix therefore launches every sandbox container inside that daemon's
namespace, not the host's.

Consequence: a breakout from a scan container lands inside the `dind`
container rather than on the host, with no access to the host's Docker socket.
This is a large improvement over mounting `/var/run/docker.sock` (which grants
effective host root to anything that can talk to the socket).

The scan workdir is a shared named volume (`scandata`, mounted at
`/var/aegis-scans`) so Strix's bind-mounts of the checkout resolve identically
in both the worker and the dind daemon. It is deliberately **not** under
`/tmp`: the dind entrypoint mounts a tmpfs over `/tmp`, which would shadow the
volume and make every bind source invalid.

### The worker shares dind's network namespace

The worker runs with `network_mode: "service:dind"`. This is required, not
incidental: Strix resolves a sandbox's Caido proxy port to the address the
*daemon* published it on (`127.0.0.1:<port>` inside dind), so without a shared
network stack the worker's own loopback has nothing listening and every scan
fails at proxy bootstrap. The alternative — mounting the host socket so worker
and daemon coincide — would forfeit the isolation above entirely.

The sandbox containers themselves remain on the separate dind daemon; only the
worker's network stack is shared.

### What this does *not* isolate

**Scan sandboxes can reach the application network.** `dind` is attached to the
compose network, and its bridge NATs outbound traffic, so a container inside it
can open connections to Postgres and Redis. Verified against the dev stack from
inside a sandbox container:

```
postgres  REACHABLE   (172.18.0.3:5432)
redis     REACHABLE   (172.18.0.2:6379)  -> PING returns +PONG, unauthenticated
```

In the dev compose stack Postgres uses the default `aegis:aegis` credentials
and Redis requires no password, so untrusted target code that escapes its
sandbox can read and write the broker and the database directly. Treat the
`docker compose` topology as a development convenience, never as the
production isolation boundary.

## Residual risks & production hardening

The `dind` container is **privileged** — that is inherent to running a nested
Docker daemon. Before a public, multi-tenant, paid launch, strengthen it:

- **Stronger runtime isolation** — run scans under rootless Docker, [Sysbox],
  gVisor, or Firecracker microVMs so a kernel-level escape from the sandbox
  still cannot compromise the node. Prefer one isolated runner per scan/tenant.
- **Network segmentation and egress control** — this is now the highest-value
  item, not a nice-to-have: the sandbox can currently reach Postgres and Redis
  (see above). Put scan runners on a network with no route to the data tier,
  and restrict outbound traffic to the LLM API and required OSINT endpoints
  only (specs §5). Left open, a malicious target can exfiltrate data or pivot
  into the application's own services.
- **Authenticate the data tier** — require a Postgres password and set Redis
  `requirepass` even on internal networks, so reachability alone is not
  sufficient for compromise.
- **Resource limits** — cap CPU/memory/pids on the daemon and per-container to
  blunt resource-exhaustion abuse. The per-scan LLM spend cap
  (`STRIX_MAX_BUDGET_USD`) already bounds token cost.
- **Ephemeral nodes** — schedule scan workers on disposable, isolated nodes,
  not shared with the API/DB tier.

[Sysbox]: https://github.com/nestybox/sysbox

## Authorization to scan a target

Automated penetration testing must only run against systems the user is
authorized to test. Aegis requires each user to accept the scan-authorization
terms (attesting they own or are permitted to test their targets) before any
scan can be created — enforced server-side on `POST /scans`.

Repository targets carry their own check: the caller must have **write access**
on the source host (GitHub, GitLab or Bitbucket), verified server-side rather
than trusted from the dropdown. Without it a subscriber could point Aegis at
any public repository.

URL targets — web, API, LLM and MCP — cannot be verified that way, and are the
highest-risk surface on the platform. They rest entirely on the attestation.
Treat abuse reports seriously and be prepared to suspend accounts.

**Discovered assets are never scanned automatically.** Attack-surface discovery
records new hosts and notifies the organization, but stops there: a host that
resolves under a customer's domain is not proof they are authorized to attack
it — shared platforms, partner subdomains and parked names all resolve there
too. Someone has to press the button.

Discovery itself reads certificate transparency rather than probing DNS or
ports, so enumeration sends nothing at the customer's infrastructure. Only
candidate hosts are contacted, with a single HTTP GET.

## Bearer credentials: API tokens and share links

Two credentials besides the session grant access, and both are stored only as
SHA-256 digests. The plaintext is returned once, at creation, and is
unrecoverable afterwards — a leaked database must not hand an attacker the
ability to launch scans against a customer's production estate, nor the reports
describing how to attack it.

SHA-256 rather than bcrypt is deliberate: both are 256-bit random tokens with
no guessable structure, so the slow hash that protects a human-chosen password
buys nothing while costing a KDF round on every request.

- **API tokens** (`aeg_…`) act as the organization with a role of their own, so
  a CI pipeline can be given exactly the authority to launch scans and read
  reports and nothing more. They can carry an expiry, are revoked rather than
  deleted (so the audit log still resolves them), and stamp `last_used_at` so a
  stale one can be spotted.
- **Report share links** always expire — there is no permanent option, because
  a permanent URL to a document describing how to attack the customer is a leak
  with a long fuse. By default they withhold proof-of-concept code *and*
  request/response transcripts, which together are a working recipe. Views are
  counted and written to the audit log, every response is `no-store` (a report
  cached by the recipient's corporate proxy would outlive the expiry we
  promised), and the route exposes no way to reach a second report from the
  first.

## Evidence handling

Findings store what was actually observed, which means transcripts captured
from live traffic — routinely including the tester's session cookie or bearer
token. Before storage, `services/evidence.py` strips `Authorization`, `Cookie`,
`Set-Cookie`, proxy-auth and API-key headers, and password-like body fields,
keeping the field *names* so the reader can still see that a request carried
auth. Each field is truncated from both ends, since evidence is read on every
report render and a response body can be megabytes.

This matters because reports leave the building: they are exported as PDFs,
filed into Jira and Linear, and handed to auditors over share links.

## Other controls (implemented)

- **Secrets at rest** — every stored credential is encrypted with AES-256-GCM
  (`EncryptedString`): source-host tokens for GitHub, GitLab and Bitbucket, the
  BYOK LLM key, Jira and Linear tokens, the outbound-webhook secret, and
  grey-box passwords. All are write-only over the API — reads return a boolean
  saying whether one is set, never the value.
- **Auth** — short-lived JWT access tokens + refresh rotation; passwords hashed
  with bcrypt.
- **Rate limiting** — Redis-backed limits on abuse-prone auth endpoints.
- **Tenant isolation** — enforced at the organization: a scan, a finding and a
  triage verdict are reachable only through a target, and a target only through
  an organization the caller is a member of. Asking for an organization you do
  not belong to returns 404, not 403 — whether a team exists is not something
  an outsider gets to learn.
- **Role checks** — every endpoint declares its minimum role, and nobody can
  grant a role (or issue a token) above their own. The last owner of an
  organization cannot be removed, since an organization with no owner has no
  subscription behind it and nobody who can restore one.
- **Audit log** — append-only, recording who did what, and never the value of a
  credential. Writing an event can never fail the action it records.
