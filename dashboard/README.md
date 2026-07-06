# Aegis Dashboard

The authenticated web app for Aegis — sign in with GitHub, connect repositories,
launch Strix pentests, and read validated findings. It's a standalone Next.js
app kept separate from the marketing site in [`../frontend`](../frontend) but
sharing its design tokens.

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
│       ├── repos/            # connect repos, launch scans
│       └── scans/            # history list + [id] detailed report
├── components/               # AppShell, AuthGuard, NewScanDialog, ui primitives
└── lib/                      # api client, tokens, auth context, formatters, types
```

## Billing

The `/billing` page shows the current plan, usage vs. limits, and a plan
catalog. Subscribing opens Stripe Checkout; existing subscribers get the Stripe
billing portal. Scanning and connecting repos are gated on an active
subscription — unentitled actions return **402** and the UI shows an "Upgrade"
prompt (see `NewScanAction` and the 402 handling in the repos / new-scan flows).

## Roadmap (not yet built)

- Password reset / email verification flows
