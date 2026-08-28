"""File a single finding in whichever issue tracker the team uses.

The tracker is chosen per call, defaulting to whatever the organization has
configured (Jira, Linear, or GitHub issues). Wherever it lands, the resulting
URL is stored on the finding's triage row — keyed by ``(target, fingerprint)``
— so a re-scan that reports the same issue links to the existing ticket
instead of opening a duplicate. That key is why triage, not the vulnerability
row, is the right home: the row is replaced on every scan; the ticket is not.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.enums import IssueTracker
from app.models.scan import Scan
from app.models.user import User
from app.models.vulnerability import Vulnerability
from app.services import (
    github_app,
    installation_service,
    issue_trackers,
    triage_service,
)

logger = logging.getLogger("aegis.finding_issue")


def default_tracker(user: User) -> IssueTracker:
    """The tracker this account files to unless told otherwise."""
    if user.has_jira:
        return IssueTracker.JIRA
    if user.has_linear:
        return IssueTracker.LINEAR
    return IssueTracker.GITHUB


def create_issue(
    db: Session,
    scan: Scan,
    vuln: Vulnerability,
    user: User,
    tracker: Optional[IssueTracker] = None,
) -> tuple[Optional[str], IssueTracker, Optional[str], str]:
    """File (or return) the issue for one finding.

    Returns ``(url, tracker, key, code)`` where code is ``""`` on success,
    ``"already"`` when a ticket existed, or one of ``no_fingerprint`` /
    ``no_installation`` / ``not_configured`` / ``tracker_error``.
    """
    if not vuln.fingerprint:
        return None, tracker or IssueTracker.GITHUB, None, "no_fingerprint"

    verdict = triage_service.get_verdict(db, scan.target_id, vuln.fingerprint)
    if verdict is not None and verdict.github_issue_url:
        return (
            verdict.github_issue_url,
            verdict.issue_tracker or IssueTracker.GITHUB,
            verdict.issue_key,
            "already",
        )

    chosen = tracker or default_tracker(user)
    title = issue_title(vuln)
    body = issue_body(scan, vuln)

    try:
        if chosen is IssueTracker.JIRA:
            url, key = issue_trackers.create_jira_issue(
                site_url=user.jira_url or "",
                email=user.jira_email or "",
                api_token=user.jira_api_token or "",
                project_key=user.jira_project_key or "",
                title=title,
                body=body,
            )
        elif chosen is IssueTracker.LINEAR:
            url, key = issue_trackers.create_linear_issue(
                api_key=user.linear_api_key or "",
                team_id=user.linear_team_id or "",
                title=title,
                body=body,
            )
        else:
            url, key = _create_github_issue(db, scan, user, title, body)
            if url is None:
                return None, chosen, None, "no_installation"
    except issue_trackers.IssueTrackerError as exc:
        logger.warning("Filing failed for finding %s in %s: %s", vuln.id, chosen.value, exc)
        return None, chosen, None, "tracker_error"
    except github_app.GitHubAppError as exc:
        logger.warning("GitHub issue creation failed for finding %s: %s", vuln.id, exc)
        return None, chosen, None, "tracker_error"

    triage_service.record_issue(
        db,
        target_id=scan.target_id,
        fingerprint=vuln.fingerprint,
        tracker=chosen,
        url=url,
        key=key or None,
    )
    return url, chosen, key or None, ""


def _create_github_issue(
    db: Session, scan: Scan, user: User, title: str, body: str
) -> tuple[Optional[str], str]:
    """Open a GitHub issue on the scanned repository, if the App is installed."""
    repo_full = scan.target.name  # "owner/repo"
    installation_id = scan.github_installation_id
    if not installation_id:
        inst = installation_service.get_by_account(
            db, scan.target.organization_id, repo_full.split("/", 1)[0]
        )
        if inst is None:
            return None, ""
        installation_id = inst.installation_id

    token = github_app.get_installation_token(installation_id)
    url = github_app.create_issue(token, repo_full, title=title, body=body)
    # GitHub has no short key of its own; the issue number is what people cite.
    return url, url.rsplit("/", 1)[-1] if url else ""


# --- Pure helpers ---------------------------------------------------------
def issue_title(vuln: Vulnerability) -> str:
    severity = str(getattr(vuln.severity, "value", vuln.severity)).capitalize()
    return f"[Aegis/{severity}] {vuln.title}"


def issue_body(scan: Scan, vuln: Vulnerability) -> str:
    """The finding as markdown, with its evidence and a link back to Aegis."""
    severity = str(getattr(vuln.severity, "value", vuln.severity)).capitalize()
    meta = [f"**Severity:** {severity}"]
    if vuln.cvss_score is not None:
        meta.append(f"**CVSS:** {vuln.cvss_score:.1f}")
    if vuln.owasp_category:
        meta.append(f"**Class:** {vuln.owasp_category}")
    if vuln.file_path:
        meta.append(f"**Location:** `{vuln.file_path}`")

    lines = [" · ".join(meta), "", "## Description", "", vuln.description.strip()]
    if vuln.poc_code:
        lines += ["", "## Proof of concept", "", "```", vuln.poc_code.strip(), "```"]

    # getattr, not attribute access: the PDF/SARIF renderers and these
    # helpers are exercised with SimpleNamespace stand-ins in tests.
    evidence = getattr(vuln, "evidence", None) or {}
    if evidence.get("request") or evidence.get("response"):
        lines += ["", "## Evidence"]
        if evidence.get("request"):
            lines += ["", "Request:", "```http", str(evidence["request"]).strip(), "```"]
        if evidence.get("response"):
            lines += ["", "Response:", "```http", str(evidence["response"]).strip(), "```"]
        if evidence.get("observed_at"):
            lines += ["", f"Observed at {evidence['observed_at']}."]

    if vuln.remediation:
        lines += ["", "## Remediation", "", vuln.remediation.strip()]
    lines += [
        "",
        "---",
        f"Reported by Aegis — "
        f"[view the full scan report →]({settings.DASHBOARD_URL}/scans/{scan.id})",
    ]
    return "\n".join(lines)
