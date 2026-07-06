"""GitHub App integration for CI/CD pull-request scanning.

Responsibilities:
  * Authenticate as the App (RS256 JWT) and mint per-installation tokens.
  * Verify inbound webhook signatures (HMAC-SHA256).
  * Post/return a findings comment and a check run on a pull request.

Network calls use a synchronous ``httpx.Client`` (matching the sync DB/worker
layers). Pure helpers (signature check, comment formatting, check conclusion)
are dependency-light and unit-tested.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import datetime, timezone
from typing import Any, Optional

import httpx
from jose import jwt

from app.core.config import settings

GITHUB_API_BASE = "https://api.github.com"
_TIMEOUT = httpx.Timeout(15.0)

# Marker embedded in our PR comment so re-scans update it instead of piling on.
_COMMENT_MARKER = "<!-- aegis-scan -->"

_SEVERITY_ORDER = ["critical", "high", "medium", "low", "info"]
_SEVERITY_EMOJI = {
    "critical": "🔴", "high": "🟠", "medium": "🟣", "low": "🔵", "info": "⚪",
}


class GitHubAppError(Exception):
    """Raised when a GitHub App API call or configuration fails."""


# --- Configuration --------------------------------------------------------
def is_configured() -> bool:
    return bool(
        settings.GITHUB_APP_ID
        and settings.GITHUB_APP_PRIVATE_KEY
        and settings.GITHUB_APP_WEBHOOK_SECRET
    )


def install_url() -> str:
    slug = settings.GITHUB_APP_SLUG
    return f"https://github.com/apps/{slug}/installations/new" if slug else ""


def _private_key() -> str:
    raw = settings.GITHUB_APP_PRIVATE_KEY
    if not raw:
        raise GitHubAppError("GitHub App private key is not configured")
    key = raw.replace("\\n", "\n")
    if "-----BEGIN" in key:
        return key
    try:  # otherwise assume a base64-encoded PEM
        return base64.b64decode(raw).decode("utf-8")
    except Exception as exc:  # noqa: BLE001
        raise GitHubAppError("GITHUB_APP_PRIVATE_KEY is not a valid PEM or base64 PEM") from exc


# --- Authentication -------------------------------------------------------
def create_app_jwt() -> str:
    """A short-lived RS256 JWT identifying the App itself."""
    now = datetime.now(timezone.utc)
    claims = {
        # Backdate iat by 60s to tolerate minor clock skew (GitHub guidance).
        "iat": int(now.timestamp()) - 60,
        "exp": int(now.timestamp()) + 540,  # max 10 minutes
        "iss": settings.GITHUB_APP_ID,
    }
    return jwt.encode(claims, _private_key(), algorithm="RS256")


def _app_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {create_app_jwt()}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _token_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def get_installation_token(installation_id: str) -> str:
    """Exchange the App JWT for a short-lived installation access token."""
    url = f"{GITHUB_API_BASE}/app/installations/{installation_id}/access_tokens"
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.post(url, headers=_app_headers())
    except httpx.HTTPError as exc:
        raise GitHubAppError(f"Could not reach GitHub: {exc}") from exc
    if resp.status_code != 201:
        raise GitHubAppError(
            f"Failed to mint installation token (HTTP {resp.status_code})"
        )
    return resp.json()["token"]


def get_installation_account(installation_id: str) -> str:
    """Return the account login (org/user) an installation belongs to."""
    url = f"{GITHUB_API_BASE}/app/installations/{installation_id}"
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.get(url, headers=_app_headers())
    except httpx.HTTPError as exc:
        raise GitHubAppError(f"Could not reach GitHub: {exc}") from exc
    if resp.status_code != 200:
        raise GitHubAppError(f"Unknown installation (HTTP {resp.status_code})")
    return (resp.json().get("account") or {}).get("login", "")


# --- Webhooks -------------------------------------------------------------
def verify_webhook_signature(payload: bytes, signature_header: Optional[str]) -> bool:
    """Constant-time check of the ``X-Hub-Signature-256`` header."""
    secret = settings.GITHUB_APP_WEBHOOK_SECRET
    if not secret or not signature_header:
        return False
    digest = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    expected = f"sha256={digest}"
    return hmac.compare_digest(expected, signature_header)


# --- PR comment (upsert) --------------------------------------------------
def upsert_pr_comment(
    token: str, repo_full_name: str, pr_number: int, body: str
) -> None:
    """Update our existing findings comment on the PR, or create it."""
    body = f"{_COMMENT_MARKER}\n{body}"
    existing_id = _find_aegis_comment(token, repo_full_name, pr_number)
    with httpx.Client(timeout=_TIMEOUT) as client:
        if existing_id is not None:
            resp = client.patch(
                f"{GITHUB_API_BASE}/repos/{repo_full_name}/issues/comments/{existing_id}",
                headers=_token_headers(token),
                json={"body": body},
            )
        else:
            resp = client.post(
                f"{GITHUB_API_BASE}/repos/{repo_full_name}/issues/{pr_number}/comments",
                headers=_token_headers(token),
                json={"body": body},
            )
    if resp.status_code not in (200, 201):
        raise GitHubAppError(f"Failed to post PR comment (HTTP {resp.status_code})")


def _find_aegis_comment(
    token: str, repo_full_name: str, pr_number: int
) -> Optional[int]:
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.get(
                f"{GITHUB_API_BASE}/repos/{repo_full_name}/issues/{pr_number}/comments",
                headers=_token_headers(token),
                params={"per_page": 100},
            )
    except httpx.HTTPError:
        return None
    if resp.status_code != 200:
        return None
    for comment in resp.json():
        if _COMMENT_MARKER in (comment.get("body") or ""):
            return comment.get("id")
    return None


# --- Check runs -----------------------------------------------------------
def create_check_run(
    token: str, repo_full_name: str, head_sha: str, *, name: str = "Aegis Security"
) -> Optional[str]:
    """Create an in-progress check run; returns its id (None on failure)."""
    body = {
        "name": name,
        "head_sha": head_sha,
        "status": "in_progress",
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.post(
                f"{GITHUB_API_BASE}/repos/{repo_full_name}/check-runs",
                headers=_token_headers(token),
                json=body,
            )
    except httpx.HTTPError:
        return None
    if resp.status_code != 201:
        return None
    return str(resp.json().get("id"))


def update_check_run(
    token: str,
    repo_full_name: str,
    check_run_id: str,
    *,
    conclusion: str,
    title: str,
    summary: str,
) -> None:
    """Complete a check run with a conclusion (success/failure/neutral)."""
    body = {
        "status": "completed",
        "conclusion": conclusion,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "output": {"title": title, "summary": summary},
    }
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.patch(
            f"{GITHUB_API_BASE}/repos/{repo_full_name}/check-runs/{check_run_id}",
            headers=_token_headers(token),
            json=body,
        )
    if resp.status_code != 200:
        raise GitHubAppError(f"Failed to update check run (HTTP {resp.status_code})")


# --- Git data (auto-fix pull requests) -----------------------------------
def get_default_branch(token: str, repo_full_name: str) -> tuple[str, str]:
    """Return the repo's default branch name and its head commit SHA."""
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.get(
            f"{GITHUB_API_BASE}/repos/{repo_full_name}", headers=_token_headers(token)
        )
        if resp.status_code != 200:
            raise GitHubAppError(f"Could not read repository (HTTP {resp.status_code})")
        branch = resp.json().get("default_branch", "main")

        ref = client.get(
            f"{GITHUB_API_BASE}/repos/{repo_full_name}/git/ref/heads/{branch}",
            headers=_token_headers(token),
        )
        if ref.status_code != 200:
            raise GitHubAppError(f"Could not read default branch (HTTP {ref.status_code})")
    return branch, ref.json()["object"]["sha"]


def create_branch(token: str, repo_full_name: str, branch: str, from_sha: str) -> None:
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.post(
            f"{GITHUB_API_BASE}/repos/{repo_full_name}/git/refs",
            headers=_token_headers(token),
            json={"ref": f"refs/heads/{branch}", "sha": from_sha},
        )
    if resp.status_code != 201:
        raise GitHubAppError(f"Could not create branch (HTTP {resp.status_code})")


def delete_branch(token: str, repo_full_name: str, branch: str) -> None:
    """Best-effort branch deletion (used to clean up when no fix applied)."""
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            client.delete(
                f"{GITHUB_API_BASE}/repos/{repo_full_name}/git/refs/heads/{branch}",
                headers=_token_headers(token),
            )
    except httpx.HTTPError:
        pass


def get_file_content(
    token: str, repo_full_name: str, path: str, ref: str
) -> tuple[str, str]:
    """Return a file's decoded text and its blob SHA at ``ref``."""
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.get(
            f"{GITHUB_API_BASE}/repos/{repo_full_name}/contents/{path}",
            headers=_token_headers(token),
            params={"ref": ref},
        )
    if resp.status_code != 200:
        raise GitHubAppError(f"Could not read {path} (HTTP {resp.status_code})")
    data = resp.json()
    try:
        text = base64.b64decode(data["content"]).decode("utf-8")
    except (KeyError, ValueError, UnicodeDecodeError) as exc:
        raise GitHubAppError(f"Could not decode {path}") from exc
    return text, data["sha"]


def put_file_content(
    token: str,
    repo_full_name: str,
    path: str,
    text: str,
    *,
    branch: str,
    blob_sha: str,
    message: str,
) -> None:
    body = {
        "message": message,
        "content": base64.b64encode(text.encode("utf-8")).decode("ascii"),
        "branch": branch,
        "sha": blob_sha,
    }
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.put(
            f"{GITHUB_API_BASE}/repos/{repo_full_name}/contents/{path}",
            headers=_token_headers(token),
            json=body,
        )
    if resp.status_code not in (200, 201):
        raise GitHubAppError(f"Could not commit {path} (HTTP {resp.status_code})")


def create_pull_request(
    token: str, repo_full_name: str, *, title: str, head: str, base: str, body: str
) -> str:
    """Open a PR and return its html_url."""
    with httpx.Client(timeout=_TIMEOUT) as client:
        resp = client.post(
            f"{GITHUB_API_BASE}/repos/{repo_full_name}/pulls",
            headers=_token_headers(token),
            json={"title": title, "head": head, "base": base, "body": body},
        )
    if resp.status_code != 201:
        raise GitHubAppError(f"Could not open pull request (HTTP {resp.status_code})")
    return resp.json()["html_url"]


# --- Pure helpers ---------------------------------------------------------
def fail_severities() -> set[str]:
    return {
        s.strip().lower()
        for s in settings.GITHUB_CHECK_FAIL_SEVERITIES.split(",")
        if s.strip()
    }


def check_conclusion(counts: dict[str, int]) -> str:
    """``failure`` if any blocking-severity finding exists, else ``success``."""
    blocking = fail_severities()
    if any(counts.get(sev, 0) for sev in blocking):
        return "failure"
    return "success"


def check_summary(total: int, counts: dict[str, int]) -> tuple[str, str]:
    """(title, summary markdown) for a check run based on findings."""
    if total == 0:
        return ("No vulnerabilities found", "Aegis found no exploitable vulnerabilities. ✅")
    conclusion = check_conclusion(counts)
    verdict = "Blocking issues found" if conclusion == "failure" else "Issues found"
    title = f"{total} finding{'s' if total != 1 else ''} — {verdict}"
    return (title, _severity_table(counts))


def _severity_table(counts: dict[str, int]) -> str:
    lines = ["| Severity | Count |", "| --- | --- |"]
    for sev in _SEVERITY_ORDER:
        n = counts.get(sev, 0)
        if n:
            lines.append(f"| {_SEVERITY_EMOJI[sev]} {sev.capitalize()} | {n} |")
    return "\n".join(lines)


def format_findings_comment(
    counts: dict[str, int],
    findings: list[Any],
    *,
    total: int,
    report_url: str = "",
) -> str:
    """A concise PR comment summarizing the scan's findings (markdown)."""
    if total == 0:
        body = "## 🛡️ Aegis Security\n\nNo exploitable vulnerabilities found in this pull request. ✅"
        return body

    conclusion = check_conclusion(counts)
    badge = "❌ **Blocking**" if conclusion == "failure" else "⚠️ **Review**"
    parts = [
        "## 🛡️ Aegis Security",
        f"{badge} — {total} validated finding{'s' if total != 1 else ''} in this pull request.",
        "",
        _severity_table(counts),
        "",
    ]

    top = sorted(
        findings,
        key=lambda f: _SEVERITY_ORDER.index(_sev(f)) if _sev(f) in _SEVERITY_ORDER else 99,
    )[:10]
    if top:
        parts.append("### Findings")
        for f in top:
            sev = _sev(f)
            emoji = _SEVERITY_EMOJI.get(sev, "•")
            title = _attr(f, "title") or "Untitled finding"
            loc = _attr(f, "file_path")
            suffix = f" — `{loc}`" if loc else ""
            parts.append(f"- {emoji} **{sev.capitalize()}**: {title}{suffix}")
        if len(findings) > len(top):
            parts.append(f"- …and {len(findings) - len(top)} more")
        parts.append("")

    if report_url:
        parts.append(f"[View the full report →]({report_url})")
    return "\n".join(parts)


def _sev(finding: Any) -> str:
    value = _attr(finding, "severity")
    return str(getattr(value, "value", value)).lower()


def _attr(obj: Any, name: str) -> Any:
    return obj.get(name) if isinstance(obj, dict) else getattr(obj, name, None)
