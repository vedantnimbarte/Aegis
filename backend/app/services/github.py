"""GitHub OAuth service.

Implements the server-side half of the GitHub OAuth web flow:
  1. Exchange the short-lived `code` (from the frontend redirect) for a
     GitHub access token.
  2. Fetch the authenticated user's profile (and a verified email).

Uses a synchronous `httpx.Client` because the calling endpoints are sync
`def` (run in FastAPI's threadpool), matching the sync DB session layer.
"""
from __future__ import annotations

from typing import Any, Optional

import httpx

from app.core.config import settings

GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_API_BASE = "https://api.github.com"
_TIMEOUT = httpx.Timeout(10.0)


class GitHubOAuthError(Exception):
    """Raised when any step of the GitHub OAuth exchange fails."""


def exchange_code_for_token(code: str, redirect_uri: Optional[str] = None) -> str:
    """Trade an OAuth `code` for a GitHub user access token."""
    if not settings.GITHUB_CLIENT_ID or not settings.GITHUB_CLIENT_SECRET:
        raise GitHubOAuthError("GitHub OAuth is not configured on the server")

    data: dict[str, str] = {
        "client_id": settings.GITHUB_CLIENT_ID,
        "client_secret": settings.GITHUB_CLIENT_SECRET,
        "code": code,
    }
    effective_redirect = redirect_uri or settings.GITHUB_OAUTH_REDIRECT_URI
    if effective_redirect:
        data["redirect_uri"] = effective_redirect

    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.post(
                GITHUB_TOKEN_URL,
                data=data,
                headers={"Accept": "application/json"},
            )
    except httpx.HTTPError as exc:
        raise GitHubOAuthError(f"Could not reach GitHub: {exc}") from exc

    if resp.status_code != 200:
        raise GitHubOAuthError(
            f"GitHub token exchange failed (HTTP {resp.status_code})"
        )

    payload: dict[str, Any] = resp.json()
    # GitHub returns HTTP 200 with an `error` field on bad/expired codes.
    if "error" in payload:
        raise GitHubOAuthError(
            payload.get("error_description") or payload["error"]
        )

    token = payload.get("access_token")
    if not token:
        raise GitHubOAuthError("GitHub did not return an access token")
    return token


def fetch_github_user(access_token: str) -> dict[str, Any]:
    """Fetch the authenticated user's profile and a verified email address."""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.get(f"{GITHUB_API_BASE}/user", headers=headers)
            if resp.status_code != 200:
                raise GitHubOAuthError(
                    f"Failed to fetch GitHub profile (HTTP {resp.status_code})"
                )
            profile: dict[str, Any] = resp.json()

            # A user's public email may be null; fetch verified emails instead.
            # Requires the `user:email` OAuth scope.
            email = profile.get("email")
            if not email:
                email = _fetch_primary_email(client, headers)
    except httpx.HTTPError as exc:
        raise GitHubOAuthError(f"Could not reach GitHub: {exc}") from exc

    return {
        "id": str(profile["id"]),
        "login": profile.get("login"),
        "email": email,
        "name": profile.get("name"),
        "avatar_url": profile.get("avatar_url"),
    }


def _fetch_primary_email(client: httpx.Client, headers: dict[str, str]) -> Optional[str]:
    resp = client.get(f"{GITHUB_API_BASE}/user/emails", headers=headers)
    if resp.status_code != 200:
        return None
    emails: list[dict[str, Any]] = resp.json()
    primary = next(
        (e for e in emails if e.get("primary") and e.get("verified")), None
    )
    if primary:
        return primary["email"]
    verified = next((e for e in emails if e.get("verified")), None)
    return verified["email"] if verified else None
