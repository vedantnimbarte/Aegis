<div align="center">

<img src="assets/logo.png" alt="Aegis" width="120" height="120">

# Aegis

**Continuous, AI-driven penetration testing that acts like a real hacker.**

</div>

Aegis is a SaaS platform powered by the open-source [Strix](https://github.com/usestrix/strix) AI engine. It runs continuous penetration tests against source repositories, running applications, APIs, and — increasingly the part nobody else tests — LLM applications and MCP servers.

Two things separate it from a scanner. Every finding is **validated by exploitation**, with the request, the response and the proof-of-concept output stored alongside it. And every fix can be **verified**: Aegis re-runs the original exploit and records whether it still works, so "fixed" is a claim with a receipt rather than someone's say-so.

> **Status:** Feature-complete against the PRD and the follow-on roadmap. Enterprise SSO/SCIM remains per-contract (see [Roadmap](#roadmap)).

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Option A: Docker Compose (recommended)](#option-a-docker-compose-recommended)
  - [Option B: Local Python environment](#option-b-local-python-environment)
  - [Running the dashboard (frontend)](#running-the-dashboard-frontend)
- [Configuration](#configuration)
- [Database Migrations](#database-migrations)
- [API Reference](#api-reference)
- [Data Model](#data-model)
- [Scan Lifecycle](#scan-lifecycle)
- [Organizations, Roles & the Audit Log](#organizations-roles--the-audit-log)
- [Evidence & Verification Retests](#evidence--verification-retests)
- [Testing the AI Layer](#testing-the-ai-layer)
- [Attack-Surface Discovery](#attack-surface-discovery)
- [Compliance Reports & Sharing](#compliance-reports--sharing)
- [Outbound Webhook](#outbound-webhook)
- [Security Model](#security-model)
- [Deployment](#deployment)
- [Roadmap](#roadmap)
- [License](#license)

---

## Features

**What gets tested**

- **Targets, not just repositories** — a target is a source repository, a live web app, an HTTP API, an LLM application, or an MCP server. Black-box testing needs no source at all.
- **AI-layer testing** — LLM applications, agents and MCP servers assessed against the OWASP LLM Top 10 (2026), the Top 10 for Agentic Applications, and the MCP Top 10.
- **API-aware testing** — routes are inferred from the checkout into an OpenAPI description and handed to the agents, so BOLA/BFLA/IDOR testing has real endpoints instead of a crawl.
- **Attack-surface discovery** — certificate transparency finds hosts under a watched domain and reports them; discovered assets are never scanned automatically.
- **Source hosts** — GitHub, GitLab and Bitbucket, plus a CI script for everywhere else.

**Why the findings are trustworthy**

- **Validated by exploitation** — a candidate that cannot be exploited is discarded, not reported.
- **Evidence on every finding** — the request, the response, the PoC output, the target and commit, the model that produced it, and when. Credentials are redacted before storage.
- **Verification retests** — re-run one finding's exploit on demand. A run that cannot complete is recorded as *inconclusive*, never as fixed.
- **Attack chains** — findings that compose into a worse outcome are grouped and scored as one, the way a human pentester reports.
- **Triage that survives re-scans** — verdicts are keyed to a finding's fingerprint, so a false positive dismissed once stays dismissed.

**Fitting into a team**

- **Organizations and roles** — viewer / member / admin / owner, with an append-only audit log. A viewer seat is the auditor's read-only account.
- **Pull-request gate that survives contact** — the check fails only on findings the PR *introduced*; pre-existing debt is reported and never blocking. Policy is per target.
- **Fixes** — one pull request bundling every fixable finding, then a retest to prove it worked.
- **Issue tracking** — GitHub issues, Jira, or Linear, deduplicated by fingerprint.
- **Compliance pack** — scope, methodology, control mappings, stated limitations and a signed attestation letter, plus expiring share links for auditors and prospects.
- **Cost transparency** — spend per target and cost per validated finding, from the engine's own usage report.
- **Integrations** — bring-your-own LLM key (BYOK), Slack, a signed outbound webhook, and API tokens for CI.

## Architecture

Aegis uses a decoupled, service-oriented architecture that handles long-running Strix pentests asynchronously while keeping the web tier responsive.

```
                       ┌──────────────┐
                       │  Dashboard   │  Next.js (./dashboard)
                       │ (React/Vercel)│
                       └──────┬───────┘
                              │ HTTPS / JWT
                       ┌──────▼───────┐        ┌──────────────┐
                       │  FastAPI API │◄──────►│  PostgreSQL  │
                       │  /api/v1/*   │        │  (metadata)  │
                       └──────┬───────┘        └──────────────┘
                              │ enqueue job
                       ┌──────▼───────┐
                       │ Redis broker │
                       └──────┬───────┘
                              │ consume
                       ┌──────▼───────┐        ┌──────────────┐
                       │ Celery worker│──────► │ Strix Docker │  ephemeral,
                       │              │        │  container   │  network-isolated
                       └──────────────┘        └──────────────┘
```

1. The API creates a `pending` scan record and enqueues a job to Redis.
2. A Celery worker picks up the job, marks it `running`, prepares the target
   (a clone for a repository; nothing to prepare for a URL), and runs Strix,
   which spins up its own isolated sandbox container.
3. On completion the worker parses Strix's JSON report, stores each finding with
   its evidence, composes attack chains, marks the scan `completed`, and tears
   the working directory down.

Celery Beat runs two recurring jobs beside this: due scheduled scans, and
attack-surface discovery sweeps.

## Tech Stack

| Layer          | Technology                                            |
| -------------- | ----------------------------------------------------- |
| API            | FastAPI (Python 3.12), Uvicorn                        |
| Database       | PostgreSQL 16, SQLAlchemy 2.0, Alembic migrations     |
| Job queue      | Celery 5 + Redis 7                                     |
| Auth / crypto  | JWT (python-jose), bcrypt, AES-256-GCM (cryptography) |
| Integrations   | GitHub OAuth + App, GitLab, Bitbucket, Jira, Linear, Slack, Stripe (all httpx) |
| Security engine| Strix (autonomous AI pentesting agents)               |
| Reporting      | fpdf2 (PDF + compliance pack), SARIF 2.1.0            |
| Dashboard      | Next.js, Tailwind CSS, React Query (`./dashboard`)   |

## Project Structure

```
Aegis/
├── docker-compose.yml        # Local stack: db, redis, api, worker, beat, metrics
├── prd.md / specs.md         # Original PRD and technical specification
├── ops/
│   ├── ci/                   # aegis-scan.sh + recipes for non-GitHub CI
│   ├── backup/               # DB backup / restore scripts
│   ├── prometheus/, grafana/ # Observability stack
├── dashboard/                # Next.js app (see dashboard/README.md)
└── backend/
    ├── Dockerfile
    ├── alembic/versions/     # Migrations (0001 … 0013_organizations_and_targets)
    ├── tests/                # pytest — pure logic, no database required
    └── app/
        ├── main.py           # FastAPI entrypoint + health check
        ├── api/
        │   ├── deps.py       # Principal: JWT or API token -> org + role
        │   └── v1/endpoints/ # auth, users, orgs, targets, scans, schedules,
        │                     # github, billing, dashboard, shares
        ├── core/             # config, security, encryption, rate limiting
        ├── db/               # SQLAlchemy base + session
        ├── models/           # organizations, targets, scans, findings, triage…
        ├── schemas/          # Pydantic request/response models
        ├── services/         # one concern each — the interesting ones being
        │                     # evidence, retest, attack_paths, ai_testing,
        │                     # api_spec, asm, gate, compliance
        └── workers/          # Celery app + scan / schedule / discovery tasks
```

Most of `services/` is deliberately pure — no database, no settings — so the
rules that matter (what counts as evidence, when a fix is verified, what blocks
a merge, what a chain is) are unit-tested directly.

## Getting Started

### Prerequisites

- [Docker](https://docs.docker.com/get-docker/) & Docker Compose
- (For local, non-Docker runs) Python 3.12+

### Option A: Docker Compose (recommended)

This brings up PostgreSQL, Redis, the API, the Celery worker, Celery Beat
(the recurring-scan scheduler), and the Next.js dashboard together.

```bash
# 1. Configure environment
cp backend/.env.example backend/.env
# edit backend/.env — generate secrets (see Configuration below)

# 1b. Data-tier credentials for docker compose itself. Compose fails fast if
#     these are unset — there is no default password. The DATABASE_URL and
#     REDIS_URL in backend/.env must use the same two values.
cp .env.example .env
python -c "import secrets;print('POSTGRES_PASSWORD=' + secrets.token_urlsafe(24))" >> .env
python -c "import secrets;print('REDIS_PASSWORD=' + secrets.token_urlsafe(24))" >> .env

# 2. Build and start the stack
docker compose up --build

# 3. Apply database migrations (in a second terminal)
docker compose exec api alembic upgrade head
```

- API: http://localhost:8000
- Interactive docs (Swagger): http://localhost:8000/docs
- Health check: http://localhost:8000/health
- Dashboard: http://localhost:3001

> The worker mounts the host Docker socket (`/var/run/docker.sock`) so Strix can launch sibling containers.

### Option B: Local Python environment

```bash
cd backend
python -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env              # then edit .env

# Requires local PostgreSQL and Redis running
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# In a separate terminal, run the worker:
celery -A app.workers.celery_app.celery worker --loglevel=info
```

### Running the dashboard (frontend)

Option A (Docker Compose) already runs the dashboard dev server with hot reload
at http://localhost:3001. To run it **without Docker** (e.g. alongside the
backend from Option B):

```bash
cd dashboard
npm install
cp .env.example .env.local        # set NEXT_PUBLIC_API_BASE_URL etc.
npm run dev                       # http://localhost:3001
```

Point `NEXT_PUBLIC_API_BASE_URL` at the API (default
`http://localhost:8000/api/v1`) and make sure the API's `BACKEND_CORS_ORIGINS`
allows `http://localhost:3001`. See [dashboard/README.md](dashboard/README.md)
for the full environment and auth details.

## Configuration

All configuration is read from environment variables (or `backend/.env`). Start from `backend/.env.example`. Key values:

| Variable                    | Description                                                        |
| --------------------------- | ------------------------------------------------------------------ |
| `DATABASE_URL`              | PostgreSQL DSN, e.g. `postgresql+psycopg://aegis:aegis@localhost:5432/aegis` |
| `REDIS_URL`                 | Redis URL used as the Celery broker/result backend                 |
| `JWT_SECRET_KEY`            | Secret for signing JWTs (min 32 chars)                             |
| `ACCESS_TOKEN_EXPIRE_MINUTES` / `REFRESH_TOKEN_EXPIRE_DAYS` | Token lifetimes         |
| `ENCRYPTION_KEY`            | URL-safe base64 of 32 bytes; AES-256-GCM key for GitHub tokens at rest |
| `GITHUB_CLIENT_ID` / `GITHUB_CLIENT_SECRET` / `GITHUB_OAUTH_REDIRECT_URI` | GitHub OAuth app credentials |
| `STRIPE_SECRET_KEY` / `STRIPE_WEBHOOK_SECRET` | Stripe billing credentials                       |
| `STRIX_LLM`                 | LLM Strix uses, e.g. `openai/gpt-4o`                              |
| `OPENAI_API_KEY` / `ANTHROPIC_API_KEY` | LLM provider keys forwarded to Strix containers        |
| `BACKEND_CORS_ORIGINS`      | Comma-separated allowed origins for CORS                          |

Generate the required secrets:

```bash
# JWT secret
python -c "import secrets; print(secrets.token_urlsafe(48))"

# Encryption key (AES-256-GCM)
python -c "import os, base64; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
```

> `.env` and `.env.*` are git-ignored (except `.env.example`). Never commit real secrets.

## Database Migrations

Schema is owned by Alembic (the app does **not** auto-create tables).

```bash
# Apply the latest migrations
alembic upgrade head

# Create a new migration after changing models
alembic revision --autogenerate -m "describe change"
```

## API Reference

All endpoints are versioned under `/api/v1`.

| Endpoint              | Method | Auth | Description                                          |
| --------------------- | ------ | ---- | ---------------------------------------------------- |
| `/health`             | GET    | No   | Service health / environment                         |
| `/auth/register`      | POST   | No   | Create an account with email + password; issues a JWT |
| `/auth/login`         | POST   | No   | Authenticate with email + password; issues a JWT     |
| `/auth/forgot-password` | POST | No   | Email a password-reset link (always 202, anti-enumeration) |
| `/auth/reset-password`  | POST | No   | Set a new password with a reset token; issues a JWT  |
| `/auth/verify-email`  | POST   | No   | Confirm an email address with the emailed token      |
| `/auth/resend-verification` | POST | Yes | Re-send the verification email to the signed-in user |
| `/auth/github`        | POST   | No   | Handles GitHub OAuth callback and issues a JWT       |
| `/users/me`           | GET    | Yes  | Current user profile and subscription status         |
| `/users/me/integrations` | PATCH | Yes | LLM key, Slack, webhook, Jira/Linear, source-host tokens |
| `/orgs`               | GET/POST | Yes | Organizations you belong to; create one (or a client workspace) |
| `/orgs/current`       | GET/PATCH | Yes | The acting organization, your role, and report branding |
| `/orgs/current/members` | GET/POST | Yes | Seats and roles (admin to change)                 |
| `/orgs/current/members/{id}` | PATCH/DELETE | Yes | Re-role or remove a member             |
| `/orgs/current/audit` | GET    | Yes  | Append-only record of who did what (admin)           |
| `/orgs/current/tokens` | GET/POST | Yes | API tokens for CI; plaintext returned once (admin) |
| `/orgs/current/tokens/{id}` | DELETE | Yes | Revoke a token                                |
| `/targets`            | GET/POST | Yes | Targets of any kind; create one by URL              |
| `/targets/available`  | GET    | Yes  | Repositories connectable from a source host          |
| `/targets/repos`      | POST   | Yes  | Connect a repository (write access verified on the host) |
| `/targets/{id}`       | GET/PATCH/DELETE | Yes | Read, edit gate policy and budget, or remove |
| `/targets/{id}/spec`  | GET    | Yes  | The OpenAPI description derived from source          |
| `/targets/{id}/greybox` | GET/PUT/DELETE | Yes | Authenticated-testing config (secrets write-only) |
| `/scans`              | GET/POST | Yes | Scan history; trigger a scan (gated by plan credits) |
| `/scans/{id}`         | GET    | Yes  | Status and metadata of a specific scan               |
| `/scans/{id}/progress` | GET   | Yes  | Live agent progress while a scan runs                |
| `/scans/{id}/cancel`  | POST   | Yes  | Stop a pending or running scan                       |
| `/scans/{id}/report`  | GET    | Yes  | Findings with evidence, attack chains, and the diff  |
| `/scans/{id}/report.pdf` | GET | Yes  | PDF; `?compliance_pack=true` for the auditor's document |
| `/scans/{id}/report.sarif` | GET | Yes | SARIF 2.1.0 for GitHub code scanning              |
| `/scans/{id}/shares`  | GET/POST | Yes | Expiring public links to this report                |
| `/scans/{id}/shares/{share_id}` | DELETE | Yes | Revoke a share link immediately            |
| `/scans/{id}/autofix` | POST   | Yes  | Open a PR applying Strix's suggested fixes for the scan |
| `/scans/{id}/findings/{fid}/triage` | PATCH | Yes | Record a verdict, carried across re-scans |
| `/scans/{id}/findings/{fid}/retest` | POST | Yes | Re-run this finding's exploit to verify a fix |
| `/scans/{id}/findings/{fid}/issue` | POST | Yes | File it in GitHub, Jira, or Linear         |
| `/dashboard/summary`  | GET    | Yes  | Current posture across every target                  |
| `/dashboard/costs`    | GET    | Yes  | Spend per target and cost per validated finding      |
| `/schedules`          | GET/POST | Yes | Recurring scan schedules                            |
| `/schedules/{id}`     | PATCH/DELETE | Yes | Update or delete a schedule                     |
| `/github/app`         | GET    | Yes  | GitHub App config + the organization's installations |
| `/github/installations` | POST | Yes  | Link an App installation (admin)                     |
| `/github/installations/{id}` | DELETE | Yes | Unlink an App installation                     |
| `/github/webhook`     | POST   | No   | GitHub App webhook (signature-verified) — PR scans   |
| `/shared/{token}`     | GET    | No   | A shared report, by its link token                   |
| `/shared/{token}/report.pdf` | GET | No | The shared report as a PDF                        |
| `/billing/summary`    | GET    | Yes  | Plan, credit/seat usage vs. limits, and the catalog  |
| `/billing/checkout`   | POST   | Yes  | Start a Stripe Checkout session for a self-serve tier |
| `/billing/compliance-report/{scan_id}` | POST | Yes | Buy a one-off audit-ready report      |
| `/billing/portal`     | POST   | Yes  | Open the Stripe billing portal to manage a plan      |
| `/billing/webhook`    | POST   | No   | Stripe webhook (signature-verified) — syncs subscriptions |

Explore and try endpoints interactively at `/docs` (Swagger UI) or `/redoc`.

**Authentication.** A user's JWT, or an API token (`Authorization: Bearer aeg_…`)
issued from the dashboard. A request acts in the caller's own organization
unless it carries an `X-Aegis-Org` header naming another one they belong to, so
single-team customers never encounter it. See
[ops/ci/README.md](ops/ci/README.md) for driving the API from CI.

## Data Model

Tenancy is the organization. A user is an identity; everything else hangs off
an organization they are a member of.

- **users** — `id`, `email`, encrypted host tokens and integration credentials, `subscription_tier`, `stripe_customer_id`
- **organizations** — `id`, `name`, `slug`, `owner_user_id`, `parent_id` (client workspaces), report branding
- **org_memberships** — `organization_id`, `user_id`, `role` (`viewer`/`member`/`admin`/`owner`)
- **audit_events** — append-only `action`, actor, subject, and detail
- **targets** — `id`, `organization_id`, `kind` (`repo`/`web`/`api`/`llm`/`mcp`), `name`, `provider`, `clone_url`, `url`, gate policy, spend cap
- **scans** — `id`, `target_id`, `status`, `scan_mode`, `trigger` (incl. `retest`), `cost_usd`, `engine_model`, `attack_chains`
- **vulnerabilities** — `id`, `scan_id`, `severity`, `title`, `description`, `poc_code`, `remediation`, `fingerprint`, `suggested_fix`, `evidence`
- **finding_triage** — keyed `(target_id, fingerprint)`: the verdict, the tracker issue, and the retest outcome — all of which outlive the scan that produced them
- **api_tokens** / **report_shares** — hashed bearer credentials for CI and for shared reports

> **Upgrading an existing install:** `0013_organizations_and_targets` renames
> `repositories` to `targets` and gives every existing user a personal
> organization owning their data. Scan history, findings and triage verdicts
> survive intact — the alternative was asking every customer to re-baseline,
> which throws away the diffing that makes the product useful.

## Scan Lifecycle

1. **Trigger** — `POST /scans` creates a `Scans` record with status `pending`.
2. **Queue** — the API enqueues `run_strix_scan(scan_id)` to Redis.
3. **Prepare** — a Celery worker marks the scan `running` and prepares the
   target. A repository target is shallow-cloned into a per-scan working dir
   (private repos use the owner's host credential, scrubbed from all logs); a
   web, API, LLM or MCP target is addressed by URL and needs no checkout at all.
4. **Plan** — the worker decides what the agents are told, by target kind:
   an AI-layer target gets the OWASP GenAI test plan, a repository gets the
   routes inferred from its source, a grey-box target gets a mode-`0600`
   instruction file with its credentials (never on the command line), and a
   retest gets one finding's proof of concept and nothing else.
5. **Execute** — the worker runs the Strix CLI headless:
   ```bash
   strix -n --target <checkout and/or url> --scan-mode <quick|standard|deep> \
         [--instruction-file …] [--max-budget-usd <target cap>]
   ```
   Strix launches its own isolated Docker sandbox. Exit codes `0` (clean) and
   `2` (findings) are both success.
6. **Ingest** — the worker parses `strix_runs/<run>/vulnerabilities.json`.
7. **Store** — findings are persisted with their evidence (redacted and
   bounded), fingerprinted for triage and diffing, composed into attack chains,
   and the scan is marked `completed`. A retest instead writes its verdict to
   the finding's triage row. Any failure marks the scan `failed`.

## Auto-Fix Pull Requests

During ingestion, Aegis stores the concrete before/after code fixes Strix
suggests for each finding (`vulnerabilities.suggested_fix`). From a completed
scan's report, **Generate fix PR** bundles every fixable finding into one pull
request: it resolves the GitHub App installation for the repo owner, branches
off the default branch, applies each stored fix to the affected files (a literal
`fix_before → fix_after` replacement, skipping any that no longer match so
unrelated code is never touched), and opens a PR. The PR URL is cached on the
scan so it's generated once. Requires the GitHub App installed on the repo owner
and an active subscription; gated with **402** (no subscription) / **400**
(`reason: no_installation`).

Opening the PR is half the job. Once it merges, use **Verify fix** on each
finding to re-run its original exploit and record whether it still works — see
[Evidence & Verification Retests](#evidence--verification-retests).

## Authenticated (Grey-Box) Testing

A target can carry a grey-box config so Strix tests **behind the login
wall**: a live `target_url` plus test credentials (`login_url`, `username`,
`password`, and free-form `extra` for headers/cookies/tokens). Secrets are
encrypted at rest (AES-256-GCM) and never returned by the API — reads expose
only `has_password` / `has_extra`.

At scan time the worker adds the live URL as an extra Strix `--target` and
passes an **instruction file** (mode `0600`, in the ephemeral scan workdir —
never on the command line) describing the target and credentials. It applies to
every scan of that target — manual, scheduled, and pull-request — and an
AI-layer target folds the same credentials into its own test plan. Manage it
from the Targets page ("Auth" on each target card).

A grey-box URL on a repository target is also what makes **fix verification**
possible: a retest re-runs the exploit against a running system, which is
exactly the claim that re-reading source cannot support.

## CI/CD GitHub App

A dedicated GitHub App (separate from the login OAuth app) brings Aegis into the
pull-request workflow:

1. An admin installs the App on their repos/org; GitHub redirects to the
   dashboard's Settings page with an `installation_id` they **claim** (stored in
   `installations`, mapping installs → *organization*, so PR scanning keeps
   working after whoever clicked install leaves).
2. On a `pull_request` (opened/synchronize/reopened) webhook — HMAC-SHA256
   signature-verified — Aegis maps the installation to the organization,
   auto-connects the repo as a target, and dispatches a **quick** scan of the PR
   head commit (gated the same as manual scans).
3. The worker clones the PR commit with a short-lived **installation token**
   (RS256 App JWT → installation access token), opens an in-progress **check
   run**, and on completion posts/updates a findings **comment** and completes
   the check run.

**The gate only fails on new findings.** A team that turns on scanning inherits
whatever their codebase already had, and a check that fails on that backlog is
a check somebody removes in week two — which costs more security than it ever
bought. So the check run compares against the previous scan and blocks only on
findings this pull request introduced; pre-existing ones are listed in the
comment, marked, and never blocking. New findings are flagged ✨ in the comment.

Policy is per target (**Targets → settings**): which severities block, and
whether to consider only new findings. The platform default is
`GITHUB_CHECK_FAIL_SEVERITIES`; an explicitly empty policy means report-only,
which is a real choice for a legacy service.

For GitLab, Jenkins, CircleCI and everything else, see
[ops/ci/README.md](ops/ci/README.md).

Configure `GITHUB_APP_ID`, `GITHUB_APP_SLUG`, `GITHUB_APP_PRIVATE_KEY` (PEM or
base64), and `GITHUB_APP_WEBHOOK_SECRET`; point the App's webhook at
`/api/v1/github/webhook` and its post-install setup URL at the dashboard's
`/settings`.

## Scheduled Scans

Any target can have a recurring schedule (daily / weekly / monthly).
**Celery Beat** ticks every few minutes and runs `enqueue_due_scheduled_scans`,
which finds schedules whose `next_run_at` has passed, advances them, and
dispatches a scan for each — but only when the organization is still entitled;
otherwise it's skipped and retried next period. Manage schedules from the
dashboard's Targets page (`GET/POST /schedules`, `PATCH/DELETE /schedules/{id}`).

A second beat task, `run_asset_discovery`, sweeps discovery-enabled targets for
new hosts — see [Attack-Surface Discovery](#attack-surface-discovery). Recurring
scans of a known list are scheduling; finding the host nobody remembered
deploying is the other half.

## Organizations, Roles & the Audit Log

Targets, scans, findings, integrations and history belong to an
**organization**, not to a person. A user reaches them through a membership
carrying a role:

| Role | Can |
| --- | --- |
| `viewer` | Read reports. Nothing that spends money or attacks anything — this is the seat you give an auditor. |
| `member` | Everything a viewer can, plus connect targets, launch scans, triage, retest, and file issues. |
| `admin` | Everything a member can, plus manage members, API tokens, GitHub App installations, and read the audit log. |
| `owner` | Everything, including billing. |

A request acts in the caller's own organization unless it carries
`X-Aegis-Org`. Billing stays on the owner's Stripe customer: an organization
reads its entitlement from `owner_user_id`, so there is never a second,
competing notion of who pays.

**Client workspaces** (Enterprise) nest one organization under another. An
agency's admins inherit their role in every client workspace beneath it, usage
bills to the agency, and reports can carry the agency's own branding. Role
inheritance is one level deep on purpose.

**The audit log** is append-only and records the action, the actor, the subject
and enough context to answer "who changed this" — never the value of a
credential. Recording an event can never fail the action it records.

## Evidence & Verification Retests

The most common complaint about AI pentesting is findings nobody can reproduce,
and one caught hallucination costs a tool the benefit of the doubt on
everything else it reports. Two mechanisms answer that.

**Evidence.** Every finding stores what was actually observed: the request, the
response, the proof-of-concept output, the exact target and commit, the engine
and model that produced it, and when. Credentials are stripped before storage
(`Authorization`, `Cookie`, API-key headers, and password-ish body fields), and
each field is truncated from both ends so the outcome of a transcript survives.
A finding with no observation stores no evidence at all rather than dressing up
"we ran at 10:04" as proof.

**Retests.** *Verify fix* on any finding re-runs its original proof of concept
against the live target and asks one question: does this exploit still work?

| Outcome | Meaning |
| --- | --- |
| `fixed` | The engine completed and the exploit no longer succeeds. Triage flips to *fixed* and the receipt is stored. |
| `still_vulnerable` | The exploit still works. The fresh transcript replaces the old one. |
| `inconclusive` | The run could not complete, so nothing was proven. |

`inconclusive` deliberately never collapses into `fixed`. A tool that reports a
vulnerability as remediated because it crashed before checking is worse than
one that reports nothing.

Retests cost no scan credits — charging for verification would discourage the
step that makes a "fixed" verdict worth anything. A repository target with no
live URL cannot be retested and says so, rather than re-reading the same source
and calling that proof.

## Testing the AI Layer

Prompt injection now tops the OWASP LLM Top 10, and most pentest vendors cannot
test the model layer at all. Aegis treats an LLM application or an MCP server
as a first-class target kind and assesses it against the published lists:

- **OWASP Top 10 for LLM Applications (2026)** — prompt injection (direct,
  indirect and multi-turn), sensitive information disclosure, improper output
  handling, excessive agency, system-prompt leakage, unbounded consumption.
- **OWASP Top 10 for Agentic Applications** — tool misuse, identity and
  privilege abuse, agentic supply chain.
- **OWASP MCP Top 10 (beta)** — unauthenticated servers, tool poisoning and
  description injection, unsafe tool implementations, resource exposure.

What keeps this from becoming noise is the reporting bar: a finding requires a
concrete security consequence, the exact prompt and response, and a probe that
reproduces. Model tone, hallucinated facts, and objectionable-but-harmless
output are explicitly not vulnerabilities.

## Attack-Surface Discovery

A target can be watched for new hosts. Discovery reads **certificate
transparency** rather than brute-forcing DNS — every public TLS certificate is
logged, so CT names the hosts an organization actually deployed without sending
a packet at the customer's infrastructure, which is the polite order of
operations when the next step is launching exploits. Each candidate is probed
once over HTTPS then HTTP to see what is live.

New hosts are recorded as targets and the organization is notified. They are
**never scanned automatically**: a host that resolves under a domain is not
proof that the customer is authorized to attack it. Sweeps run on the beat
schedule (`ASM_INTERVAL_HOURS`) and are capped at `ASM_MAX_ASSETS_PER_SWEEP` so
one wildcard zone cannot fill the targets table.

## Compliance Reports & Sharing

`GET /scans/{id}/report.pdf?compliance_pack=true` produces the document an
auditor expects rather than a findings list: an executive summary, the scope
and testing window, the methodology, control mappings, stated limitations, and
a signed **letter of attestation** on its own page.

Two honesty rules shape it. The methodology says plainly that testing was
performed by autonomous agents under a named human attestor — auditors ask, and
a report that obscures it fails the question badly. And control mappings are
described as *evidence toward* a control, never as a pass: no tool can certify
SOC 2, and claiming to is how a customer gets burned in an audit they trusted
us for.

**Share links** hand one report to someone without an account —
`POST /scans/{id}/shares` returns a URL that expires (always; there is no
"never" option) and by default withholds proof-of-concept code and request
transcripts, which together are a working recipe against the customer's
production system. Only the token digest is stored, views are counted and
audited, and every response is `no-store`.

## Outbound Webhook

Set a webhook URL and a shared secret in **Settings → Integrations** and Aegis
POSTs one JSON body per finished scan, so findings can reach a SIEM or an
internal service without Aegis building that integration.

```json
{
  "event": "scan.completed",
  "scan": { "id": "…", "repository": "acme/api", "status": "completed",
            "report_url": "https://…/scans/…" },
  "findings": { "total": 3, "by_severity": { "critical": 1, "high": 1,
                "medium": 1, "low": 0, "info": 0 } }
}
```

| Header | Value |
| --- | --- |
| `X-Aegis-Event` | the event name, currently always `scan.completed` |
| `X-Aegis-Timestamp` | Unix seconds at delivery |
| `X-Aegis-Signature` | `sha256=<hex>` |

The signature is HMAC-SHA256 over `<timestamp>.<raw body>` using your secret.
The timestamp is inside the signed material rather than only in a header, so a
captured delivery cannot be replayed with a fresh one: reject a stale timestamp
and the signature cannot be recomputed without the secret.

Verify against the **raw** body — Aegis serializes once and signs the exact
bytes it sends, so re-encoding a parsed object will not match:

```python
import hashlib, hmac, time

def verify(secret: str, headers, body: bytes, tolerance: int = 300) -> bool:
    timestamp = headers["X-Aegis-Timestamp"]
    if abs(time.time() - int(timestamp)) > tolerance:
        return False
    expected = "sha256=" + hmac.new(
        secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, headers["X-Aegis-Signature"])
```

Deliveries are best-effort and are never retried: a webhook that cannot be
reached must not turn a completed scan into a failed one. Treat the report API
as the source of truth.

## Security Model

- **Auth** — stateless JWTs with short-lived (15 min) access tokens plus a refresh-token mechanism. Passwords are bcrypt-hashed.
- **Password reset** — a short-lived reset JWT is bound to a fingerprint of the user's current password hash, so it self-invalidates the moment the password changes (single-use, no server-side token store). `forgot-password` always returns the same response to avoid account enumeration. Reset links are emailed via SMTP, or logged when SMTP is unconfigured (dev).
- **Email verification** — email/password sign-ups start unverified and receive a verification link; GitHub logins are trusted as verified. Sign-in works while unverified, but launching scans / connecting repos is gated with a **403** (`reason: email_not_verified`) until the email is confirmed. The dashboard surfaces a banner with a resend action.
- **Token encryption** — every stored credential (GitHub/GitLab/Bitbucket tokens, the BYOK LLM key, Jira and Linear tokens, webhook secrets, grey-box passwords) is encrypted at rest with AES-256-GCM and is write-only over the API: reads return only a boolean saying whether it is set.
- **Tenant isolation** — enforced at the organization. A scan, a finding and a triage verdict are reachable only through a target, and a target only through an organization the caller is a member of.
- **Roles** — every endpoint declares the minimum role it needs (`viewer` for reads, `member` to spend or attack, `admin` for members/tokens/installations, `owner` for billing). Nobody can grant a role above their own.
- **Bearer credentials** — API tokens and report share links are stored as SHA-256 digests; the plaintext is shown once and is unrecoverable. Share links always expire.
- **Evidence redaction** — captured transcripts are stripped of `Authorization`, `Cookie`, API-key headers and password-like body fields before they are stored, because a report gets shared with auditors and prospects.
- **Rate limiting** — Redis-backed limits on abuse-prone auth endpoints (login/register/forgot/reset/GitHub) to blunt brute-force and signup/email spam.
- **Scan authorization** — automated pentesting may only target authorized systems; users must accept the scan-authorization terms (a **403** `reason: scan_terms_required` gate) before any scan runs.
- **Sandbox isolation** — untrusted target code runs in Strix containers on a dedicated Docker-in-Docker daemon (not the host socket), so an escape is contained. Per-scan LLM spend is capped (`STRIX_MAX_BUDGET_USD`). See [SECURITY.md](SECURITY.md) for the full model and production hardening (rootless/sysbox/gVisor, egress limits).

## Billing & Subscription Gating

Scanning is gated behind an active Stripe subscription. Tiers and their
entitlements live in
[`billing_plans.py`](backend/app/services/billing_plans.py):

| Tier       | Targets   | Scan credits / mo | Seats     | Purchase            |
| ---------- | --------- | ----------------- | --------- | ------------------- |
| Free       | 0         | 0                 | 1         | — (default)         |
| Starter    | 3         | 20                | 2         | Self-serve Checkout |
| Pro        | Unlimited | 200 (+ overage)   | 10        | Self-serve Checkout |
| Enterprise | Unlimited | Custom            | Unlimited | Contact sales       |

**Why credits rather than "unlimited scans".** Every scan spends LLM tokens,
and `scans.cost_usd` records exactly how much. An unlimited tier on a metered
engine has no cost floor: one customer running deep scans of a monorepo hourly
costs more than the subscription. So a plan buys credits, priced by depth —
**quick 1, standard 3, deep 10** — and **retests are free**, because charging
for verification would discourage the step that makes a "fixed" verdict mean
anything.

Pro and above keep working past the included allowance and bill the difference;
Starter stops, so a small plan cannot run up a surprise invoice. Failing a
customer's pipeline at month-end is worse than an invoice — but only for
customers who chose that trade.

A one-off **compliance report** is sold separately
(`POST /billing/compliance-report/{scan_id}`), because it answers a different
question — "give me the document my auditor will accept" — and usually arrives
with a deadline rather than a monitoring need.

- **Gate** — `POST /scans` and `POST /targets` return **402** with
  `{message, reason}` (`reason` ∈ `no_subscription` / `scan_quota` /
  `target_quota` / `seat_quota`) when the organization isn't entitled. The
  dashboard turns these into an "Upgrade" prompt.
- **Checkout / portal** — `POST /billing/checkout` creates a Stripe Checkout
  session for Starter/Pro; `POST /billing/portal` opens the customer portal.
- **Webhooks** — `POST /billing/webhook` verifies the Stripe signature and
  syncs `subscription_status`, `subscription_tier`, and the current period end
  onto the user (`checkout.session.completed`, `customer.subscription.*`).

Configure `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_PRICE_STARTER`,
`STRIPE_PRICE_PRO`, and `DASHBOARD_URL` (see `.env.example`). Point a Stripe
webhook at `/api/v1/billing/webhook` (locally: `stripe listen --forward-to
localhost:8000/api/v1/billing/webhook`).

## Deployment

CI runs on every push/PR via [`.github/workflows/ci.yml`](.github/workflows/ci.yml):
backend unit tests (`pytest`) and a dashboard type-check (`tsc --noEmit`).

Both services are containerized:

- **Backend / worker** — `backend/Dockerfile` (the worker image sets
  `INSTALL_STRIX=true`). Deploy to any container host (AWS ECS, DigitalOcean App
  Platform, Fly.io) with a managed PostgreSQL and Redis. Run migrations
  (`alembic upgrade head`) on release and inject secrets via the platform's
  secret store (never bake them into the image).
- **Dashboard** — `dashboard/Dockerfile` produces a standalone Next.js server,
  or deploy it straight to Vercel from source. Set `NEXT_PUBLIC_API_BASE_URL`
  to the public API URL at build time.

Cloud provisioning (RDS/Redis, DNS, TLS, the ECS/Vercel projects themselves)
is environment-specific and lives with your infra, not this repo.

**Observability** — `docker compose up` also starts Prometheus (`:9090`) and
Grafana (`:3002`, admin/admin by default) with a provisioned datasource and an
"Aegis Overview" dashboard (API rate/latency, scan task throughput). The API
exposes metrics at `/metrics`; a `celery-exporter` scrapes scan task events.

**Operations & security** — see [OPERATIONS.md](OPERATIONS.md) for DB backup /
restore and the migration-rollback runbook, and [SECURITY.md](SECURITY.md) for
the sandbox isolation model and pre-launch hardening.

## Roadmap

- [x] Web dashboard (Next.js): scan history, detailed reports, PDF export
- [x] Strix orchestration and report ingestion (worker)
- [x] Stripe subscription gating and billing webhooks
- [x] CI/CD GitHub App — scan on pull requests and comment findings
- [x] Authenticated (grey-box) testing behind login walls
- [x] Auto-fix — open PRs with AI-suggested patches
- [x] Scheduled recurring scans for continuous attack-surface monitoring
- [x] BYOK — bring your own LLM key/model (Pro & above)
- [x] Slack notifications on scan completion
- [x] CI — GitHub Actions running backend tests + dashboard type-check
- [x] Organizations, roles, and an append-only audit log
- [x] Targets: live web apps, APIs, LLM applications and MCP servers
- [x] Evidence bundles and verification retests
- [x] Attack chains — findings composed into one outcome
- [x] New-findings-only pull-request gate, per-target policy
- [x] Compliance pack with attestation letter, and expiring share links
- [x] Jira and Linear filing alongside GitHub issues
- [x] GitLab and Bitbucket source hosts, plus a generic CI script
- [x] API tokens for CI and scripting
- [x] Attack-surface discovery via certificate transparency
- [x] OpenAPI inference from source, fed to the agents as routes
- [x] Cost reporting: spend per target, cost per validated finding
- [x] Client workspaces and white-label report branding (agency / MSSP)
- [ ] SAML/SSO and SCIM — deliberately not built until a contract names them.
      RBAC and the audit log carry most of the same buyer confidence at a
      fraction of the cost; these need an IdP and are provisioned per-contract.
- [ ] Mobile application testing — a separate toolchain for a different buyer.
- [ ] Network and Active Directory validation — a different market
      (Pentera, NodeZero) and a different buyer.
- [ ] On-prem / VPC deployment — real demand, but it turns every release into a
      supported-version problem. Priced as Enterprise, built against a signature.

[prd.md](prd.md) and [specs.md](specs.md) are the original product and
technical documents, kept for provenance; this README is the current
description.

## License

Proprietary — all rights reserved. See [LICENSE](LICENSE), which includes an
acceptable-use notice: Aegis may only be pointed at systems you own or are
explicitly authorized to test.
