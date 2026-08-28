"""Connect repositories from GitLab and Bitbucket, not just GitHub.

The CI story previously required installing a GitHub App, which excludes a
large share of the mid-market outright. Both hosts here work the same way as
GitHub does for connecting a repo: list what the token can see, verify the
caller can actually write to the one they picked, and hand back a clone URL.

Verification is not optional. A repository id arrives from the client, and
scanning is an active attack — so the check that the caller can push to it is
the thing standing between us and a subscriber pointing Aegis at somebody
else's code.

GitHub's own client stays in ``github.py``; it carries OAuth and App concerns
these two do not have.
"""
from __future__ import annotations

from typing import Any, Optional

import httpx

from app.core.config import settings
from app.models.enums import GitProvider

_TIMEOUT = httpx.Timeout(20.0)
_PER_PAGE = 100
_MAX_PAGES = 20


class SourceHostError(Exception):
    """Raised when a source host cannot be reached or refuses the request."""


# --- GitLab ---------------------------------------------------------------
# GitLab's access levels: 30 developer, 40 maintainer, 50 owner. Developer is
# the floor for "can change this code", which is the bar for scanning it.
_GITLAB_WRITE_ACCESS = 30


def list_gitlab_repositories(token: str) -> list[dict[str, Any]]:
    """Projects the token can see, newest first."""
    projects: list[dict[str, Any]] = []
    headers = {"PRIVATE-TOKEN": token}
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            for page in range(1, _MAX_PAGES + 1):
                resp = client.get(
                    f"{settings.GITLAB_API_URL}/projects",
                    headers=headers,
                    params={
                        "membership": "true",
                        "per_page": _PER_PAGE,
                        "page": page,
                        "order_by": "last_activity_at",
                    },
                )
                if resp.status_code != 200:
                    raise SourceHostError(
                        f"Failed to list GitLab projects (HTTP {resp.status_code})"
                    )
                batch = resp.json()
                if not isinstance(batch, list) or not batch:
                    break
                projects.extend(batch)
                if len(batch) < _PER_PAGE:
                    break
    except httpx.HTTPError as exc:
        raise SourceHostError(f"Could not reach GitLab: {exc}") from exc

    return [
        {
            "provider": GitProvider.GITLAB,
            "external_repo_id": str(project["id"]),
            "name": project.get("path_with_namespace") or project.get("name", ""),
            "clone_url": project.get("http_url_to_repo") or project.get("web_url", ""),
            "private": project.get("visibility") != "public",
            "description": project.get("description"),
        }
        for project in projects
    ]


def can_write_gitlab_project(token: str, project_id: str) -> bool:
    """Whether the token's owner has at least developer access to the project."""
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.get(
                f"{settings.GITLAB_API_URL}/projects/{project_id}",
                headers={"PRIVATE-TOKEN": token},
            )
    except httpx.HTTPError as exc:
        raise SourceHostError(f"Could not reach GitLab: {exc}") from exc

    if resp.status_code in (403, 404):
        return False
    if resp.status_code != 200:
        raise SourceHostError(
            f"Could not verify GitLab project access (HTTP {resp.status_code})"
        )

    permissions = resp.json().get("permissions") or {}
    levels = [
        (permissions.get(scope) or {}).get("access_level", 0)
        for scope in ("project_access", "group_access")
    ]
    return max(levels, default=0) >= _GITLAB_WRITE_ACCESS


# --- Bitbucket ------------------------------------------------------------
def list_bitbucket_repositories(token: str) -> list[dict[str, Any]]:
    """Repositories the token can administer or write to."""
    repos: list[dict[str, Any]] = []
    headers = {"Authorization": f"Bearer {token}"}
    url: Optional[str] = f"{settings.BITBUCKET_API_URL}/repositories"
    params: Optional[dict[str, Any]] = {"role": "contributor", "pagelen": _PER_PAGE}

    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            for _ in range(_MAX_PAGES):
                if not url:
                    break
                resp = client.get(url, headers=headers, params=params)
                if resp.status_code != 200:
                    raise SourceHostError(
                        f"Failed to list Bitbucket repositories (HTTP {resp.status_code})"
                    )
                body = resp.json()
                repos.extend(body.get("values") or [])
                # Bitbucket paginates with an absolute `next` URL that already
                # carries the query string, so params must not be resent.
                url = body.get("next")
                params = None
    except httpx.HTTPError as exc:
        raise SourceHostError(f"Could not reach Bitbucket: {exc}") from exc

    return [
        {
            "provider": GitProvider.BITBUCKET,
            "external_repo_id": str(repo.get("uuid") or repo.get("full_name", "")),
            "name": repo.get("full_name", ""),
            "clone_url": _bitbucket_clone_url(repo),
            "private": repo.get("is_private", True),
            "description": repo.get("description"),
        }
        for repo in repos
        if repo.get("full_name")
    ]


def _bitbucket_clone_url(repo: dict[str, Any]) -> str:
    for link in (repo.get("links") or {}).get("clone") or []:
        if link.get("name") == "https":
            return link.get("href", "")
    return (repo.get("links") or {}).get("html", {}).get("href", "")


def can_write_bitbucket_repository(token: str, full_name: str) -> bool:
    """Whether the token grants write on the repository.

    Bitbucket's uuid form is unusable as a path segment, so connection is
    keyed on ``workspace/repo`` — which the listing above already returns.
    """
    if "/" not in full_name:
        return False
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.get(
                f"{settings.BITBUCKET_API_URL}/user/permissions/repositories",
                headers={"Authorization": f"Bearer {token}"},
                params={"q": f'repository.full_name="{full_name}"'},
            )
    except httpx.HTTPError as exc:
        raise SourceHostError(f"Could not reach Bitbucket: {exc}") from exc

    if resp.status_code in (401, 403):
        return False
    if resp.status_code != 200:
        raise SourceHostError(
            f"Could not verify Bitbucket access (HTTP {resp.status_code})"
        )
    for entry in resp.json().get("values") or []:
        if entry.get("permission") in ("write", "admin"):
            return True
    return False


# --- Provider dispatch ----------------------------------------------------
def clone_username(provider: GitProvider) -> str:
    """The username half of the HTTPS credential each host expects."""
    return {
        GitProvider.GITHUB: "x-access-token",
        GitProvider.GITLAB: "oauth2",
        GitProvider.BITBUCKET: "x-token-auth",
    }.get(provider, "x-access-token")


def token_for(user, provider: GitProvider) -> Optional[str]:
    """The user's credential for a host (decrypted transparently on read)."""
    return {
        GitProvider.GITHUB: user.github_token,
        GitProvider.GITLAB: user.gitlab_token,
        GitProvider.BITBUCKET: user.bitbucket_token,
    }.get(provider)


def list_repositories(user, provider: GitProvider) -> list[dict[str, Any]]:
    """Repositories available to ``user`` on ``provider``."""
    token = token_for(user, provider)
    if not token:
        raise SourceHostError(
            f"No {provider.value} credential on file. Connect {provider.value} first."
        )
    if provider is GitProvider.GITLAB:
        return list_gitlab_repositories(token)
    if provider is GitProvider.BITBUCKET:
        return list_bitbucket_repositories(token)

    from app.services import github as github_service

    try:
        return [
            {
                "provider": GitProvider.GITHUB,
                "external_repo_id": repo["github_repo_id"],
                "name": repo["name"],
                "clone_url": repo["url"],
                "private": repo.get("private", False),
                "description": repo.get("description"),
            }
            for repo in github_service.list_user_repositories(token)
        ]
    except github_service.GitHubOAuthError as exc:
        raise SourceHostError(str(exc)) from exc


def can_write(user, provider: GitProvider, external_repo_id: str, name: str) -> bool:
    """Whether ``user`` can push to the repository they asked us to connect."""
    token = token_for(user, provider)
    if not token:
        raise SourceHostError(f"No {provider.value} credential on file.")
    if provider is GitProvider.GITLAB:
        return can_write_gitlab_project(token, external_repo_id)
    if provider is GitProvider.BITBUCKET:
        return can_write_bitbucket_repository(token, name)

    from app.services import github as github_service

    try:
        return github_service.user_can_access_repository(token, external_repo_id)
    except github_service.GitHubOAuthError as exc:
        raise SourceHostError(str(exc)) from exc
