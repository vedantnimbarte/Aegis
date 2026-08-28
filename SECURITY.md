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
scan can be created — enforced server-side on `POST /scans`. Grey-box targets
(arbitrary live URLs) are the highest-risk surface here; treat abuse reports
seriously and be prepared to suspend accounts.

## Other controls (implemented)

- **Secrets at rest** — GitHub tokens and BYOK LLM keys are encrypted with
  AES-256-GCM (`EncryptedString`).
- **Auth** — short-lived JWT access tokens + refresh rotation; passwords hashed
  with bcrypt.
- **Rate limiting** — Redis-backed limits on abuse-prone auth endpoints.
- **Tenant isolation** — every scan/repo endpoint validates ownership against
  the JWT subject.
