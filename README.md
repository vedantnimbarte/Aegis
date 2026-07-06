# Aegis

**Continuous, AI-driven penetration testing that acts like a real hacker.**

Aegis is a SaaS platform powered by the open-source [Strix](https://github.com/usestrix/strix) AI engine. It provides automated, continuous penetration testing for web applications and APIs. Unlike traditional SAST tools that flood developers with false positives, Aegis uses Strix's autonomous AI agents to dynamically execute code, validate vulnerabilities, and deliver real Proof-of-Concept (PoC) exploits with actionable remediation.

> **Status:** Early development. The backend API, data model, auth, and the Strix scan worker (repo checkout → headless Strix run → report ingestion) are in place. The frontend and billing are the next phases.

---

## Table of Contents

- [Features](#features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Getting Started](#getting-started)
  - [Option A: Docker Compose (recommended)](#option-a-docker-compose-recommended)
  - [Option B: Local Python environment](#option-b-local-python-environment)
- [Configuration](#configuration)
- [Database Migrations](#database-migrations)
- [API Reference](#api-reference)
- [Data Model](#data-model)
- [Scan Lifecycle](#scan-lifecycle)
- [Security Model](#security-model)
- [Roadmap](#roadmap)
- [License](#license)

---

## Features

- **User authentication & onboarding** — Email/password and GitHub OAuth, with stateless JWT access tokens and refresh tokens.
- **GitHub integration** — OAuth authorization for read-only access to user/organization repositories, with per-user repository selection.
- **Configurable scans** — Quick, standard, and deep scan modes with optional custom instructions (e.g. "focus on business logic and IDOR").
- **Asynchronous Strix execution** — Long-running pentests run as Celery jobs against isolated, ephemeral Docker containers so the API never blocks.
- **Validated findings** — Each vulnerability captures severity, OWASP/CVSS context, reproduction steps, a working PoC, and AI-generated remediation.
- **Subscription tiers** — Starter, Pro, and Enterprise plans, gated via Stripe (billing integration in progress).

## Architecture

Aegis uses a decoupled, service-oriented architecture that handles long-running Strix pentests asynchronously while keeping the web tier responsive.

```
                       ┌──────────────┐
                       │   Frontend   │  Next.js (planned)
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
| Frontend       | Next.js, Tailwind CSS, shadcn/ui *(planned)*          |

## Project Structure

```
Aegis/
├── docker-compose.yml        # Local stack: db, redis, api, worker
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

This brings up PostgreSQL, Redis, the API, and the Celery worker together.

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
| `/auth/github`        | POST   | No   | Handles GitHub OAuth callback and issues a JWT       |
| `/users/me`           | GET    | Yes  | Current user profile and subscription status         |
| `/repos`              | GET    | Yes  | List authorized GitHub repositories                  |
| `/repos`              | POST   | Yes  | Sync/add a repository to the user's dashboard        |
| `/scans`              | POST   | Yes  | Trigger a new Strix scan (gated by subscription/quota) |
| `/scans/{id}`         | GET    | Yes  | Status and metadata of a specific scan               |
| `/scans/{id}/report`  | GET    | Yes  | Detailed vulnerabilities and PoCs for a scan         |
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

## Security Model

- **Auth** — stateless JWTs with short-lived (15 min) access tokens plus a refresh-token mechanism.
- **Token encryption** — GitHub OAuth tokens are encrypted at rest with AES-256-GCM.
- **Tenant isolation** — every endpoint validates that the `user_id` from the JWT owns the requested `repository_id` / `scan_id`.
- **Container isolation** — Strix containers run in an isolated network with no access to host metadata or the backend database; egress is limited to the LLM API and necessary OSINT endpoints.

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

## Roadmap

- [ ] Web dashboard (Next.js): scan history, detailed reports, PDF export
- [x] Strix orchestration and report ingestion (worker)
- [x] Stripe subscription gating and billing webhooks
- [ ] CI/CD GitHub App — scan on pull requests and comment findings
- [ ] Authenticated (grey-box) testing behind login walls
- [ ] Auto-fix — open PRs with AI-suggested patches
- [ ] Scheduled recurring scans for continuous attack-surface monitoring

See [prd.md](prd.md) and [specs.md](specs.md) for full product and technical details.

## License

Proprietary — all rights reserved (subject to change).
