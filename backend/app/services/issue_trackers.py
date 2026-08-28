"""File findings in Jira and Linear.

Both are thin: authenticate, POST one issue, return ``(url, key)``. They live
together because they answer the same question and share the markdown-to-plain
conversion, and because two small clients in one module beat two modules with
an abstract base class between them.

GitHub issues stay in ``github_app`` — that integration needs App
installation tokens, which have nothing to do with these two.

Network calls use a synchronous ``httpx.Client``, matching the rest of the
service layer.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

import httpx

logger = logging.getLogger("aegis.issue_trackers")

_TIMEOUT = httpx.Timeout(15.0)

# Jira's plain-text description field has no markdown rendering, and Linear's
# does — but neither wants an unbounded PoC dump in a ticket body.
MAX_BODY_CHARS = 30_000


class IssueTrackerError(Exception):
    """Raised when a tracker rejects the request or is misconfigured."""


def _clip(text: str) -> str:
    if len(text) <= MAX_BODY_CHARS:
        return text
    return text[:MAX_BODY_CHARS] + "\n\n…[truncated — see the full Aegis report]"


# --- Jira -----------------------------------------------------------------
_MD_HEADING = re.compile(r"^#{1,6}\s*", re.MULTILINE)
_MD_FENCE = re.compile(r"^```.*$", re.MULTILINE)


def markdown_to_text(body: str) -> str:
    """Flatten markdown for a field that will not render it.

    Jira Cloud's v3 API takes Atlassian Document Format, and building ADF trees
    for arbitrary markdown is a project of its own. A readable plain-text
    ticket that links back to the full report is the right amount of work.
    """
    text = _MD_HEADING.sub("", body)
    text = _MD_FENCE.sub("", text)
    text = text.replace("**", "")
    return text.strip()


def _adf_document(body: str) -> dict:
    """Wrap plain text as a minimal Atlassian Document Format paragraph set."""
    paragraphs = [block for block in body.split("\n\n") if block.strip()]
    return {
        "type": "doc",
        "version": 1,
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": block.strip()}],
            }
            for block in paragraphs
        ]
        or [{"type": "paragraph", "content": []}],
    }


def create_jira_issue(
    *,
    site_url: str,
    email: str,
    api_token: str,
    project_key: str,
    title: str,
    body: str,
    issue_type: str = "Task",
) -> tuple[str, str]:
    """Create a Jira issue. Returns ``(browse_url, key)``."""
    if not (site_url and email and api_token and project_key):
        raise IssueTrackerError("Jira is not fully configured")

    base = site_url.rstrip("/")
    payload = {
        "fields": {
            "project": {"key": project_key},
            "summary": title[:255],
            "description": _adf_document(_clip(markdown_to_text(body))),
            "issuetype": {"name": issue_type},
        }
    }
    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.post(
                f"{base}/rest/api/3/issue",
                json=payload,
                auth=(email, api_token),
                headers={"Accept": "application/json"},
            )
    except httpx.HTTPError as exc:
        raise IssueTrackerError(f"Could not reach Jira: {exc}") from exc

    if resp.status_code >= 300:
        raise IssueTrackerError(
            f"Jira rejected the issue (HTTP {resp.status_code}): {resp.text[:400]}"
        )
    data = resp.json()
    key = data.get("key") or ""
    if not key:
        raise IssueTrackerError("Jira did not return an issue key")
    return f"{base}/browse/{key}", key


# --- Linear ---------------------------------------------------------------
LINEAR_API_URL = "https://api.linear.app/graphql"

_LINEAR_MUTATION = """
mutation CreateIssue($teamId: String!, $title: String!, $description: String!) {
  issueCreate(input: {teamId: $teamId, title: $title, description: $description}) {
    success
    issue { identifier url }
  }
}
"""


def create_linear_issue(
    *, api_key: str, team_id: str, title: str, body: str
) -> tuple[str, str]:
    """Create a Linear issue. Returns ``(url, identifier)``."""
    if not (api_key and team_id):
        raise IssueTrackerError("Linear is not fully configured")

    try:
        with httpx.Client(timeout=_TIMEOUT) as client:
            resp = client.post(
                LINEAR_API_URL,
                json={
                    "query": _LINEAR_MUTATION,
                    "variables": {
                        "teamId": team_id,
                        "title": title[:255],
                        "description": _clip(body),
                    },
                },
                headers={"Authorization": api_key, "Content-Type": "application/json"},
            )
    except httpx.HTTPError as exc:
        raise IssueTrackerError(f"Could not reach Linear: {exc}") from exc

    if resp.status_code >= 300:
        raise IssueTrackerError(
            f"Linear rejected the issue (HTTP {resp.status_code}): {resp.text[:400]}"
        )

    data = resp.json()
    # GraphQL answers 200 with an errors array, so status alone proves nothing.
    if data.get("errors"):
        message = data["errors"][0].get("message", "unknown error")
        raise IssueTrackerError(f"Linear rejected the issue: {message}")

    result = (data.get("data") or {}).get("issueCreate") or {}
    issue = result.get("issue") or {}
    if not result.get("success") or not issue.get("url"):
        raise IssueTrackerError("Linear did not return an issue")
    return issue["url"], issue.get("identifier") or ""


def resolve_tracker(user) -> Optional[str]:
    """Which tracker this account has configured, preferring the explicit ones.

    GitHub is the fallback because every repo target already has it; a team
    that wired up Jira or Linear did so precisely to stop filing in GitHub.
    """
    if getattr(user, "has_jira", False):
        return "jira"
    if getattr(user, "has_linear", False):
        return "linear"
    return "github"
