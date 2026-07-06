# Aegis Dashboard

The authenticated web app for Aegis — sign in with GitHub, connect repositories,
launch Strix pentests, and read validated findings. It's a standalone Next.js
app that talks to the FastAPI backend in [`../backend`](../backend).

## Stack

- **Next.js 14** (App Router) + React 18, TypeScript
- **Tailwind CSS** — same theme as the landing site
- **TanStack Query** — data fetching, caching, and polling of in-flight scans
- Auth: GitHub OAuth → backend-issued JWTs (access + refresh) stored client-side

## Getting started

```bash
cd dashboard
npm install
cp .env.example .env.local   # then fill in the values below
npm run dev                  # http://localhost:3001
```

### Environment

| Variable | Description |
| --- | --- |
| `NEXT_PUBLIC_API_BASE_URL` | Base URL of the FastAPI backend, e.g. `http://localhost:8000/api/v1` |
| `NEXT_PUBLIC_GITHUB_CLIENT_ID` | GitHub OAuth app client ID (public) |
| `NEXT_PUBLIC_GITHUB_REDIRECT_URI` | OAuth callback; must match the GitHub app **and** the backend's `GITHUB_OAUTH_REDIRECT_URI` (default `http://localhost:3001/auth/callback`) |

> The backend must allow the dashboard origin (`http://localhost:3001`) in
> `BACKEND_CORS_ORIGINS`.

## How auth works

`/login` offers two paths:

- **Email / password** — sign in or create an account, POSTing to
  `POST /api/v1/auth/login` or `/auth/register`.
- **GitHub** — sends the user to GitHub's OAuth authorize URL with a CSRF
  `state`; GitHub redirects back to `/auth/callback?code=…&state=…`, which
  verifies `state` and POSTs the `code` to `POST /api/v1/auth/github`.

Either path returns an access + refresh token pair, persisted in
`localStorage`. The API client attaches the access token and transparently
refreshes once on a `401` before retrying.

**Password reset** — `/forgot-password` requests a reset email; the emailed
link opens `/reset-password?token=…`, which sets a new password and signs the
user in.

**Email verification** — new email/password accounts are unverified; a banner
prompts them (with resend) and scanning is blocked until they open the emailed
`/verify-email?token=…` link. GitHub logins are already verified.

## Structure

```
dashboard/
├── app/
│   ├── layout.tsx            # fonts + providers
│   ├── providers.tsx         # React Query + AuthProvider
│   ├── login/                # email/password + GitHub sign-in
│   ├── auth/callback/        # OAuth code exchange
│   └── (app)/                # authenticated route group (guard + shell)
│       ├── page.tsx          # Overview: metrics + recent scans
│       ├── repos/            # connect repos, launch scans, schedule, grey-box auth
│       ├── scans/            # history list + [id] detailed report
│       ├── billing/          # plan, usage, Stripe checkout/portal
│       └── settings/         # GitHub App (CI/CD) integration
├── components/               # AppShell, AuthGuard, NewScanDialog, ui primitives
└── lib/                      # api client, tokens, auth context, formatters, types
```

## Billing

The `/billing` page shows the current plan, usage vs. limits, and a plan
catalog. Subscribing opens Stripe Checkout; existing subscribers get the Stripe
billing portal. Scanning and connecting repos are gated on an active
subscription — unentitled actions return **402** and the UI shows an "Upgrade"
prompt (see `NewScanAction` and the 402 handling in the repos / new-scan flows).

## Scheduled scans

Each connected repo on the Repositories page can have a recurring schedule
(daily / weekly / monthly, at a chosen depth). The dialog creates, edits,
pauses, or deletes it; the backend's Celery Beat dispatches due scans.

## GitHub App (CI/CD)

The Settings page manages the Aegis GitHub App: install it on your repos/org,
and Aegis scans every pull request and posts a findings comment + check run.
After installing, GitHub redirects back to `/settings?installation_id=…`, which
the page claims automatically.

## Authenticated (grey-box) testing

Each connected repo can carry a grey-box config (the "Auth" button on its card):
a live target URL plus test credentials so Strix scans behind the login wall.
Secrets are write-only — the form shows whether a password/extra is set and
preserves it unless you type a new value.

## Auto-fix pull requests

A completed scan's report shows a **Generate fix PR** action when any finding
has a suggested fix (each such finding also gets a "Fix" chip). It opens a
GitHub pull request applying the fixes and links to it; once opened, the report
shows a "View pull request" link instead.

## Roadmap

The MVP + PRD post-MVP scope is complete. Future ideas: GitLab/Bitbucket
support, Slack/Jira notifications, SSO/SAML.
