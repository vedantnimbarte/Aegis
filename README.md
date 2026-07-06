# Aegis

**Continuous, AI-driven penetration testing that acts like a real hacker.**

Aegis is a SaaS platform powered by the open-source [Strix](https://github.com/usestrix/strix) AI engine. It provides automated, continuous penetration testing for web applications and APIs. Unlike traditional SAST tools that flood developers with false positives, Aegis uses Strix's autonomous AI agents to dynamically execute code, validate vulnerabilities, and deliver real Proof-of-Concept (PoC) exploits with actionable remediation.

> **Status:** Feature-complete against the PRD (MVP + post-MVP): auth (email/password + GitHub OAuth, password reset, email verification), Stripe subscription gating, the full Strix scan worker, the Next.js dashboard with PDF export, scheduled recurring scans, the CI/CD GitHub App, authenticated grey-box testing, auto-fix pull requests, and Pro integrations (bring-your-own LLM key, Slack notifications).

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
- [Security Model](#security-model)
- [Deployment](#deployment)
- [Roadmap](#roadmap)
- [License](#license)

---

## Features

- **User authentication & onboarding** — Email/password and GitHub OAuth, with stateless JWT access tokens and refresh tokens.
- **GitHub integration** — OAuth authorization for read-only access to user/organization repositories, with per-user repository selection.
- **Configurable scans** — Quick, standard, and deep scan modes with optional custom instructions (e.g. "focus on business logic and IDOR").
- **Asynchronous Strix execution** — Long-running pentests run as Celery jobs against isolated, ephemeral Docker containers so the API never blocks.
- **Validated findings** — Each vulnerability captures severity, OWASP/CVSS context, reproduction steps, a working PoC, and AI-generated remediation.
- **Subscription tiers** — Starter, Pro, and Enterprise plans, gated via Stripe.
- **Pro integrations** — Bring-your-own LLM key/model (BYOK) so scans run on your own provider account, and Slack notifications when a scan finishes.

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
2. A Celery worker picks up the job, marks it `running`, and spins up an isolated Strix Docker container mounting the target repo.
3. On completion the worker parses Strix's JSON report, maps findings into the `vulnerabilities` table, marks the scan `completed`, and tears down the container.

## Tech Stack

| Layer          | Technology                                            |
| -------------- | ----------------------------------------------------- |
| API            | FastAPI (Python 3.12), Uvicorn                        |
| Database       | PostgreSQL 16, SQLAlchemy 2.0, Alembic migrations     |
| Job queue      | Celery 5 + Redis 7                                     |
| Auth / crypto  | JWT (python-jose), bcrypt, AES-256-GCM (cryptography) |
| Integrations   | GitHub OAuth (httpx), Stripe, Docker Engine API       |
| Security engine| Strix (autonomous AI pentesting agents)               |
| Dashboard      | Next.js, Tailwind CSS, React Query (`./dashboard`)   |

## Project Structure

```
Aegis/
├── docker-compose.yml        # Local stack: db, redis, api, worker, beat
├── prd.md                    # Product Requirements Document
├── specs.md                  # Technical Specification
└── backend/
    ├── Dockerfile
    ├── requirements.txt
    ├── alembic.ini
    ├── .env.example
    ├── alembic/
    │   └── versions/         # Migration scripts (0001_initial_schema)
    └── app/
        ├── main.py           # FastAPI entrypoint + health check
        ├── api/
        │   ├── deps.py       # Auth / DB dependencies
        │   └── v1/
        │       ├── router.py
        │       └── endpoints/ # auth, users, repos, scans
        ├── core/
        │   ├── config.py     # Pydantic settings
        │   ├── security.py   # JWT + password hashing
        │   └── encryption.py # AES-256-GCM token encryption
        ├── db/               # SQLAlchemy base + session
        ├── models/           # users, repositories, scans, vulnerabilities
        ├── schemas/          # Pydantic request/response models
        ├── services/         # github, user_service
        └── workers/          # Celery app + Strix scan task
```

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
| `/repos`              | GET    | Yes  | List authorized GitHub repositories                  |
| `/repos`              | POST   | Yes  | Sync/add a repository to the user's dashboard        |
| `/repos/{id}/greybox` | GET/PUT/DELETE | Yes | Authenticated-testing config (secrets write-only) |
| `/scans`              | POST   | Yes  | Trigger a new Strix scan (gated by subscription/quota) |
| `/scans/{id}`         | GET    | Yes  | Status and metadata of a specific scan               |
| `/scans/{id}/report`  | GET    | Yes  | Detailed vulnerabilities and PoCs for a scan         |
| `/scans/{id}/report.pdf` | GET | Yes  | Download the report as a PDF (compliance/sharing)    |
| `/scans/{id}/autofix` | POST   | Yes  | Open a PR applying Strix's suggested fixes for the scan |
| `/schedules`          | GET    | Yes  | List the user's recurring scan schedules             |
| `/schedules`          | POST   | Yes  | Create a recurring schedule for a repository         |
| `/schedules/{id}`     | PATCH  | Yes  | Update a schedule (cadence, depth, enabled)          |
| `/schedules/{id}`     | DELETE | Yes  | Delete a recurring schedule                          |
| `/github/app`         | GET    | Yes  | GitHub App config + the user's linked installations  |
| `/github/installations` | POST | Yes  | Link an App installation to the account (post-install) |
| `/github/installations/{id}` | DELETE | Yes | Unlink an App installation                     |
| `/github/webhook`     | POST   | No   | GitHub App webhook (signature-verified) — PR scans   |
| `/billing/summary`    | GET    | Yes  | Current plan, usage vs. limits, and plan catalog     |
| `/billing/checkout`   | POST   | Yes  | Start a Stripe Checkout session for a self-serve tier |
| `/billing/portal`     | POST   | Yes  | Open the Stripe billing portal to manage a plan      |
| `/billing/webhook`    | POST   | No   | Stripe webhook (signature-verified) — syncs subscriptions |

Explore and try endpoints interactively at `/docs` (Swagger UI) or `/redoc`.

## Data Model

- **users** — `id`, `email`, encrypted `github_token`, `subscription_tier`, `stripe_customer_id`
- **repositories** — `id`, `user_id`, `github_repo_id`, `name` (`owner/repo`), `url`
- **scans** — `id`, `repository_id`, `status` (`pending`/`running`/`completed`/`failed`), `scan_mode` (`quick`/`standard`/`deep`), `started_at`, `completed_at`
- **vulnerabilities** — `id`, `scan_id`, `severity` (`critical`/`high`/`medium`/`low`), `title`, `description`, `poc_code`, `remediation`

## Scan Lifecycle

1. **Trigger** — `POST /scans` creates a `Scans` record with status `pending`.
2. **Queue** — the API enqueues `run_strix_scan(scan_id)` to Redis.
3. **Checkout** — a Celery worker marks the scan `running` and shallow-clones the
   target repo into a per-scan working dir (private repos use the user's GitHub
   token, which is scrubbed from all logs).
4. **Execute** — the worker runs the Strix CLI headless against the checkout:
   ```bash
   strix -n --target <repo> --scan-mode <quick|standard|deep> [--instruction "..."]
   ```
   Strix itself launches an isolated Docker sandbox container via the mounted
   Docker socket (it is a Python CLI from the `strix-agent` package, not a
   single run-image). Exit codes `0` (clean) and `2` (findings) are both success.
5. **Ingest** — the worker parses `strix_runs/<run>/vulnerabilities.json`.
6. **Store** — findings are mapped into `vulnerabilities`, the scan is marked
   `completed`, and the working dir is removed. Any failure marks the scan
   `failed` with the error message.

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

## Authenticated (Grey-Box) Testing

A repository can carry a grey-box config so Strix tests **behind the login
wall**: a live `target_url` plus test credentials (`login_url`, `username`,
`password`, and free-form `extra` for headers/cookies/tokens). Secrets are
encrypted at rest (AES-256-GCM) and never returned by the API — reads expose
only `has_password` / `has_extra`.

At scan time, if the repo has a grey-box config the worker adds the live URL as
an extra Strix `--target` and passes an **instruction file** (mode `0600`, in
the ephemeral scan workdir — never on the command line) describing the target
and credentials. It applies to every scan of that repo — manual, scheduled, and
pull-request. Manage it from the Repositories page ("Auth" on each repo card).

## CI/CD GitHub App

A dedicated GitHub App (separate from the login OAuth app) brings Aegis into the
pull-request workflow:

1. A user installs the App on their repos/org; GitHub redirects to the
   dashboard's Settings page with an `installation_id` the signed-in user
   **claims** (stored in `installations`, mapping installs → account).
2. On a `pull_request` (opened/synchronize/reopened) webhook — HMAC-SHA256
   signature-verified — Aegis maps the installation to the account, auto-connects
   the repo, and dispatches a **quick** scan of the PR head commit (gated the
   same as manual scans: verified email + active subscription within quota).
3. The worker clones the PR commit with a short-lived **installation token**
   (RS256 App JWT → installation access token), opens an in-progress **check
   run**, and on completion posts/updates a findings **comment** and completes
   the check run — `failure` if any Critical/High finding is present
   (`GITHUB_CHECK_FAIL_SEVERITIES`), so it can gate merges via branch protection.

Configure `GITHUB_APP_ID`, `GITHUB_APP_SLUG`, `GITHUB_APP_PRIVATE_KEY` (PEM or
base64), and `GITHUB_APP_WEBHOOK_SECRET`; point the App's webhook at
`/api/v1/github/webhook` and its post-install setup URL at the dashboard's
`/settings`.

## Scheduled Scans

Repositories can have a recurring schedule (daily / weekly / monthly) for
continuous attack-surface monitoring. **Celery Beat** ticks every few minutes
and runs `enqueue_due_scheduled_scans`, which finds schedules whose
`next_run_at` has passed, advances them, and dispatches a scan for each — but
only when the owner is still entitled (verified email + active subscription
within quota); otherwise it's skipped and retried next period. Manage schedules
from the dashboard's Repositories page (`GET/POST /schedules`,
`PATCH/DELETE /schedules/{id}`).

## Security Model

- **Auth** — stateless JWTs with short-lived (15 min) access tokens plus a refresh-token mechanism. Passwords are bcrypt-hashed.
- **Password reset** — a short-lived reset JWT is bound to a fingerprint of the user's current password hash, so it self-invalidates the moment the password changes (single-use, no server-side token store). `forgot-password` always returns the same response to avoid account enumeration. Reset links are emailed via SMTP, or logged when SMTP is unconfigured (dev).
- **Email verification** — email/password sign-ups start unverified and receive a verification link; GitHub logins are trusted as verified. Sign-in works while unverified, but launching scans / connecting repos is gated with a **403** (`reason: email_not_verified`) until the email is confirmed. The dashboard surfaces a banner with a resend action.
- **Token encryption** — GitHub OAuth tokens are encrypted at rest with AES-256-GCM.
- **Tenant isolation** — every endpoint validates that the `user_id` from the JWT owns the requested `repository_id` / `scan_id`.
- **Rate limiting** — Redis-backed limits on abuse-prone auth endpoints (login/register/forgot/reset/GitHub) to blunt brute-force and signup/email spam.
- **Scan authorization** — automated pentesting may only target authorized systems; users must accept the scan-authorization terms (a **403** `reason: scan_terms_required` gate) before any scan runs.
- **Sandbox isolation** — untrusted target code runs in Strix containers on a dedicated Docker-in-Docker daemon (not the host socket), so an escape is contained. Per-scan LLM spend is capped (`STRIX_MAX_BUDGET_USD`). See [SECURITY.md](SECURITY.md) for the full model and production hardening (rootless/sysbox/gVisor, egress limits).

## Billing & Subscription Gating

Scanning is gated behind an active Stripe subscription, with per-tier limits
(PRD §6). Tiers and their entitlements live in
[`billing_plans.py`](backend/app/services/billing_plans.py):

| Tier       | Repositories | Scans / month | Purchase           |
| ---------- | ------------ | ------------- | ------------------ |
| Free       | 0            | 0             | — (default)        |
| Starter    | 3            | 20            | Self-serve Checkout |
| Pro        | Unlimited    | Unlimited     | Self-serve Checkout |
| Enterprise | Unlimited    | Unlimited     | Contact sales       |

- **Gate** — `POST /scans` and new-repo `POST /repos` return **402** with
  `{message, reason}` (`reason` ∈ `no_subscription` / `scan_quota` /
  `repo_quota`) when the user isn't entitled. The dashboard turns these into an
  "Upgrade" prompt.
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
- [ ] Enterprise (sales-led): SAML/SSO and Jira integration — not built; these
      need an IdP / Jira tenant and are provisioned per-contract.

See [prd.md](prd.md) and [specs.md](specs.md) for full product and technical details.

## License

Proprietary — all rights reserved. See [LICENSE](LICENSE), which includes an
acceptable-use notice: Aegis may only be pointed at systems you own or are
explicitly authorized to test.
