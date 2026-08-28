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


# GitHub caps page size at 100. The page ceiling bounds a pathological account
# (and our own latency) rather than any real limit — 20 pages is 2,000 repos.
_REPOS_PER_PAGE = 100
_MAX_REPO_PAGES = 20


def list_user_repositories(access_token: str) -> list[dict[str, Any]]:
    """List every repository the authenticated user can access.

    Paginates until GitHub returns a short page, so accounts with more than
    100 repositories see all of them. Private repos require the `repo` OAuth
    scope.
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    repos: list[dict[str, Any]] = []
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            for page in range(1, _MAX_REPO_PAGES + 1):
                resp = client.get(
                    f"{GITHUB_API_BASE}/user/repos",
                    headers=headers,
                    params={
                        "per_page": _REPOS_PER_PAGE,
                        "page": page,
                        "sort": "updated",
                        "visibility": "all",
                    },
                )
                if resp.status_code != 200:
                    raise GitHubOAuthError(
                        f"Failed to list GitHub repositories (HTTP {resp.status_code})"
                    )
                batch = resp.json()
                if not isinstance(batch, list) or not batch:
                    break
                repos.extend(batch)
                # A short page means there is no next one.
                if len(batch) < _REPOS_PER_PAGE:
                    break
    except httpx.HTTPError as exc:
        raise GitHubOAuthError(f"Could not reach GitHub: {exc}") from exc

    return [
        {
            "github_repo_id": str(repo["id"]),
            "name": repo["full_name"],
            "url": repo["html_url"],
            "private": repo.get("private", False),
            "description": repo.get("description"),
        }
        for repo in repos
    ]


def user_can_access_repository(access_token: str, github_repo_id: str) -> bool:
    """Whether the token's owner can actually see ``github_repo_id``.

    The connect endpoint takes a repo id from the client, so it has to be
    checked server-side: without this a subscriber could point Aegis at any
    public repository and launch an automated pentest against code they do
    not own.
    """
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            # /repositories/{id} resolves by id and honours the token's grants.
            resp = client.get(
                f"{GITHUB_API_BASE}/repositories/{github_repo_id}", headers=headers
            )
    except httpx.HTTPError as exc:
        raise GitHubOAuthError(f"Could not reach GitHub: {exc}") from exc

    if resp.status_code in (404, 403):
        return False
    if resp.status_code != 200:
        raise GitHubOAuthError(
            f"Could not verify repository access (HTTP {resp.status_code})"
        )

    # Visible is not sufficient: any public repo is visible to any token. Require
    # a push/admin grant, which only someone who can change the code will have.
    permissions = resp.json().get("permissions") or {}
    return bool(permissions.get("push") or permissions.get("admin"))


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
