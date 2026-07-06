"""Auto-fix: open a GitHub pull request applying Strix's suggested fixes.

Bundles every fixable finding in a scan into one PR (per the product choice):
resolve the GitHub App installation for the repo owner, branch off the default
branch, apply each finding's stored before/after fix to the affected files, and
open a pull request. The PR URL is cached on the scan so it's generated once.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.scan import Scan
from app.models.user import User
from app.services import autofix_patch, github_app, installation_service

logger = logging.getLogger("aegis.autofix")

# Cap what we list in the PR body to keep it readable.
_MAX_LISTED = 20


def generate_fix_pr(db: Session, scan: Scan, user: User) -> tuple[Optional[str], str]:
    """Open (or return) the auto-fix PR for a scan.

    Returns ``(pr_url, "")`` on success or ``(None, code)`` where code is one of
    ``already`` (already generated — url returned too), ``no_fixes``,
    ``no_installation``, or ``github_error``.
    """
    if scan.autofix_pr_url:
        return scan.autofix_pr_url, "already"

    fixable = [v for v in scan.vulnerabilities if v.suggested_fix]
    if not fixable:
        return None, "no_fixes"

    repo_full = scan.repository.name  # "owner/repo"
    owner = repo_full.split("/", 1)[0]

    installation_id = scan.github_installation_id
    if not installation_id:
        inst = installation_service.get_by_account(db, user, owner)
        if inst is None:
            return None, "no_installation"
        installation_id = inst.installation_id

    # Group every fix by the file it touches.
    by_file: dict[str, list[dict]] = {}
    for vuln in fixable:
        for fix in vuln.suggested_fix or []:
            path = fix.get("file")
            if path:
                by_file.setdefault(path, []).append(fix)
    if not by_file:
        return None, "no_fixes"

    branch = f"aegis/autofix-{str(scan.id)[:8]}"
    try:
        token = github_app.get_installation_token(installation_id)
        base_branch, base_sha = github_app.get_default_branch(token, repo_full)

        # Clean up any stale branch from a previous failed attempt, then branch.
        github_app.delete_branch(token, repo_full, branch)
        github_app.create_branch(token, repo_full, branch, base_sha)

        applied_files = applied_fixes = 0
        for path, fixes in by_file.items():
            try:
                content, blob_sha = github_app.get_file_content(token, repo_full, path, branch)
            except github_app.GitHubAppError:
                continue  # file missing/renamed since the scan — skip it
            new_content, n = autofix_patch.apply_fixes(content, fixes)
            if n and new_content != content:
                github_app.put_file_content(
                    token,
                    repo_full,
                    path,
                    new_content,
                    branch=branch,
                    blob_sha=blob_sha,
                    message=f"fix: apply Aegis security fix to {path}",
                )
                applied_files += 1
                applied_fixes += n

        if applied_files == 0:
            github_app.delete_branch(token, repo_full, branch)
            return None, "no_fixes"

        title = f"Aegis: fix {applied_fixes} security finding{'s' if applied_fixes != 1 else ''}"
        pr_url = github_app.create_pull_request(
            token,
            repo_full,
            title=title,
            head=branch,
            base=base_branch,
            body=_pr_body(scan, fixable, applied_files),
        )
    except github_app.GitHubAppError as exc:
        logger.warning("Auto-fix PR failed for scan %s: %s", scan.id, exc)
        return None, "github_error"

    scan.autofix_pr_url = pr_url
    db.commit()
    return pr_url, ""


def _pr_body(scan: Scan, fixable, applied_files: int) -> str:
    lines = [
        "## 🛡️ Aegis auto-fix",
        "",
        f"This PR applies Aegis's suggested fixes across {applied_files} "
        f"file{'s' if applied_files != 1 else ''}. **Review carefully before merging.**",
        "",
        "### Findings addressed",
    ]
    for vuln in fixable[:_MAX_LISTED]:
        sev = getattr(vuln.severity, "value", vuln.severity)
        loc = f" — `{vuln.file_path}`" if vuln.file_path else ""
        lines.append(f"- **{str(sev).capitalize()}**: {vuln.title}{loc}")
    if len(fixable) > _MAX_LISTED:
        lines.append(f"- …and {len(fixable) - _MAX_LISTED} more")
    lines += ["", f"[View the full report →]({settings.DASHBOARD_URL}/scans/{scan.id})"]
    return "\n".join(lines)
