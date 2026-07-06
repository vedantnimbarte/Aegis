"""Scan lifecycle helpers: create/dispatch, list, fetch, and report building.

Every read joins through Repository so a user can only ever see scans that
belong to a repository they own (tenant isolation, spec §5).
"""
from __future__ import annotations

import uuid
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import ScanMode, ScanTrigger, Severity
from app.models.repository import Repository
from app.models.scan import Scan
from app.models.user import User
from app.models.vulnerability import Vulnerability
from app.schemas.scan import ScanRead, ScanReport, VulnerabilityRead
from app.services import repo_service
from app.workers.tasks import run_strix_scan

# Display/order rank for severities (critical first).
_SEVERITY_RANK = {
    Severity.CRITICAL: 0,
    Severity.HIGH: 1,
    Severity.MEDIUM: 2,
    Severity.LOW: 3,
    Severity.INFO: 4,
}


def create_scan(
    db: Session,
    *,
    user: User,
    repository_id: uuid.UUID,
    scan_mode: ScanMode,
    custom_instructions: Optional[str] = None,
    trigger: ScanTrigger = ScanTrigger.MANUAL,
    github_installation_id: Optional[str] = None,
    github_pr_number: Optional[int] = None,
    github_commit_sha: Optional[str] = None,
) -> Optional[Scan]:
    """Create a `pending` scan for a user-owned repo and enqueue the worker job.

    Returns None if the repository does not exist or is not owned by the user
    (the endpoint maps that to 404, avoiding a repo-existence oracle).
    """
    repo = repo_service.get_repository(db, repository_id, user)
    if repo is None:
        return None

    scan = Scan(
        repository_id=repo.id,
        scan_mode=scan_mode,
        custom_instructions=custom_instructions,
        trigger=trigger,
        github_installation_id=github_installation_id,
        github_pr_number=github_pr_number,
        github_commit_sha=github_commit_sha,
    )
    db.add(scan)
    db.commit()
    db.refresh(scan)

    # Dispatch asynchronously. If the broker is unreachable the scan stays
    # `pending` and can be re-dispatched; we don't lose the record.
    try:
        task = run_strix_scan.delay(str(scan.id))
        scan.celery_task_id = task.id
        db.commit()
        db.refresh(scan)
    except Exception:  # noqa: BLE001 - broker/transport errors shouldn't 500 the request
        db.rollback()

    return scan


def list_scans(
    db: Session, user: User, repository_id: Optional[uuid.UUID] = None
) -> Sequence[Scan]:
    stmt = select(Scan).join(Repository).where(Repository.user_id == user.id)
    if repository_id is not None:
        stmt = stmt.where(Scan.repository_id == repository_id)
    stmt = stmt.order_by(Scan.created_at.desc())
    return db.execute(stmt).scalars().all()


def get_scan(db: Session, scan_id: uuid.UUID, user: User) -> Optional[Scan]:
    """Fetch a scan only if it belongs to a repository the user owns."""
    return db.execute(
        select(Scan)
        .join(Repository)
        .where(Scan.id == scan_id, Repository.user_id == user.id)
    ).scalar_one_or_none()


def build_report(
    db: Session, scan_id: uuid.UUID, user: User
) -> Optional[ScanReport]:
    scan = get_scan(db, scan_id, user)
    if scan is None:
        return None

    vulns = list(
        db.execute(
            select(Vulnerability).where(Vulnerability.scan_id == scan.id)
        ).scalars().all()
    )
    vulns.sort(key=lambda v: _SEVERITY_RANK.get(v.severity, 99))

    counts = {sev.value: 0 for sev in Severity}
    for v in vulns:
        counts[v.severity.value] += 1

    return ScanReport(
        scan=ScanRead.model_validate(scan),
        total=len(vulns),
        counts_by_severity=counts,
        fixable_count=sum(1 for v in vulns if v.suggested_fix),
        vulnerabilities=[VulnerabilityRead.model_validate(v) for v in vulns],
    )
