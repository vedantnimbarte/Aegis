"""Open a GitHub issue for a single finding.

Deliberately mirrors ``autofix``: resolve the GitHub App installation for the
repository owner, call the API, and cache the resulting URL. The URL is stored
on the finding's triage row — keyed by ``(repository, fingerprint)`` — so a
re-scan that reports the same issue links to the existing GitHub issue instead
of opening a duplicate.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.enums import TriageStatus
from app.models.scan import Scan
from app.models.user import User
from app.models.vulnerability import Vulnerability
from app.services import github_app, installation_service, triage_service

logger = logging.getLogger("aegis.finding_issue")


def create_issue(
    db: Session, scan: Scan, vuln: Vulnerability, user: User
) -> tuple[Optional[str], str]:
    """Open (or return) the GitHub issue for one finding.

    Returns ``(url, "")`` on success, ``(url, "already")`` when an issue was
    opened earlier, or ``(None, code)`` where code is ``no_fingerprint``,
    ``no_installation`` or ``github_error``.
    """
    if not vuln.fingerprint:
        return None, "no_fingerprint"

    verdict = triage_service.triage_map(db, scan.repository_id).get(vuln.fingerprint)
    if verdict is not None and verdict.github_issue_url:
        return verdict.github_issue_url, "already"

    repo_full = scan.repository.name  # "owner/repo"
    installation_id = scan.github_installation_id
    if not installation_id:
        inst = installation_service.get_by_account(db, user, repo_full.split("/", 1)[0])
        if inst is None:
            return None, "no_installation"
        installation_id = inst.installation_id

    try:
        token = github_app.get_installation_token(installation_id)
        url = github_app.create_issue(
            token, repo_full, title=issue_title(vuln), body=issue_body(scan, vuln)
        )
    except github_app.GitHubAppError as exc:
        logger.warning("Issue creation failed for finding %s: %s", vuln.id, exc)
        return None, "github_error"

    row = triage_service.set_triage(
        db,
        repository_id=scan.repository_id,
        fingerprint=vuln.fingerprint,
        status=verdict.status if verdict else TriageStatus.OPEN,
    )
    row.github_issue_url = url
    db.commit()
    return url, ""


# --- Pure helpers ---------------------------------------------------------
def issue_title(vuln: Vulnerability) -> str:
    severity = str(getattr(vuln.severity, "value", vuln.severity)).capitalize()
    return f"[Aegis/{severity}] {vuln.title}"


def issue_body(scan: Scan, vuln: Vulnerability) -> str:
    """The finding as GitHub-flavoured markdown, with a link back to Aegis."""
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
    if vuln.remediation:
        lines += ["", "## Remediation", "", vuln.remediation.strip()]
    lines += [
        "",
        "---",
        f"Reported by Aegis — "
        f"[view the full scan report →]({settings.DASHBOARD_URL}/scans/{scan.id})",
    ]
    return "\n".join(lines)
