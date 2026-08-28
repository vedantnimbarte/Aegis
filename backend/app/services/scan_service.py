"""Scan lifecycle helpers: create/dispatch, list, fetch, and report building.

Every read joins through Repository so a user can only ever see scans that
belong to a repository they own (tenant isolation, spec §5).
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import ScanMode, ScanStatus, ScanTrigger, Severity
from app.models.repository import Repository
from app.models.scan import Scan
from app.models.triage import FindingTriage
from app.models.user import User
from app.models.vulnerability import Vulnerability
from app.schemas.scan import (
    DashboardSummary,
    ScanDiffRead,
    ScanRead,
    ScanReport,
    VulnerabilityRead,
)
from app.services import repo_service, triage_service
from app.workers.celery_app import celery
from app.workers.tasks import run_strix_scan

logger = logging.getLogger("aegis.scans")

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


@dataclass
class FindingCounts:
    """A scan's findings, split into what still needs attention and what doesn't."""

    counts_by_severity: dict[str, int] = field(
        default_factory=lambda: {sev.value: 0 for sev in Severity}
    )
    total: int = 0
    suppressed: int = 0


def summarize_findings(
    rows: Iterable[tuple[uuid.UUID, uuid.UUID, Severity, Optional[str]]],
    suppressed_keys: frozenset[tuple[uuid.UUID, Optional[str]]],
) -> dict[uuid.UUID, FindingCounts]:
    """Group ``(scan_id, repository_id, severity, fingerprint)`` rows per scan.

    ``counts_by_severity`` deliberately excludes findings a human has triaged
    away, so a list row shows what is still outstanding rather than what was
    once reported; ``total`` counts everything, so the difference is what was
    triaged away. Pure, so it can be exercised without a database.
    """
    out: dict[uuid.UUID, FindingCounts] = {}
    for scan_id, repository_id, severity, fingerprint in rows:
        summary = out.setdefault(scan_id, FindingCounts())
        summary.total += 1
        if (repository_id, fingerprint) in suppressed_keys:
            summary.suppressed += 1
        else:
            key = severity.value if isinstance(severity, Severity) else str(severity)
            summary.counts_by_severity[key] = summary.counts_by_severity.get(key, 0) + 1
    return out


def _suppressed_keys(
    db: Session, repository_ids: Sequence[uuid.UUID]
) -> frozenset[tuple[uuid.UUID, Optional[str]]]:
    """``(repository_id, fingerprint)`` pairs a human marked as needing no action."""
    if not repository_ids:
        return frozenset()
    rows = db.execute(
        select(FindingTriage.repository_id, FindingTriage.fingerprint).where(
            FindingTriage.repository_id.in_(repository_ids),
            FindingTriage.status.in_(tuple(triage_service.SUPPRESSED_STATUSES)),
        )
    ).all()
    return frozenset((repo_id, fp) for repo_id, fp in rows)


def finding_counts(db: Session, scans: Sequence[Scan]) -> dict[uuid.UUID, FindingCounts]:
    """Severity counts for each of ``scans``, in two queries regardless of size.

    Only the columns needed for counting are selected — pulling whole
    ``Vulnerability`` rows (descriptions, PoC code, remediation markdown) just
    to add them up is what made the old client-side aggregate expensive.
    """
    scan_ids = [s.id for s in scans]
    if not scan_ids:
        return {}

    rows = db.execute(
        select(
            Vulnerability.scan_id,
            Scan.repository_id,
            Vulnerability.severity,
            Vulnerability.fingerprint,
        )
        .join(Scan, Scan.id == Vulnerability.scan_id)
        .where(Vulnerability.scan_id.in_(scan_ids))
    ).all()

    counts = summarize_findings(
        rows, _suppressed_keys(db, list({s.repository_id for s in scans}))
    )
    # A scan with no findings still gets a zeroed summary, so the UI can tell
    # "clean" apart from "not computed".
    for scan in scans:
        counts.setdefault(scan.id, FindingCounts())
    return counts


def list_scans(
    db: Session, user: User, repository_id: Optional[uuid.UUID] = None
) -> list[ScanRead]:
    """Scan history, newest first, each row carrying its finding summary."""
    stmt = select(Scan).join(Repository).where(Repository.user_id == user.id)
    if repository_id is not None:
        stmt = stmt.where(Scan.repository_id == repository_id)
    stmt = stmt.order_by(Scan.created_at.desc())
    scans = list(db.execute(stmt).scalars().all())

    counts = finding_counts(db, scans)
    out: list[ScanRead] = []
    for scan in scans:
        read = ScanRead.model_validate(scan)
        # Only a finished scan has a meaningful count; leaving it null while a
        # scan runs stops the UI rendering a premature "0 findings".
        if scan.status is ScanStatus.COMPLETED:
            summary = counts[scan.id]
            read.counts_by_severity = summary.counts_by_severity
            read.findings_total = summary.total
        out.append(read)
    return out


def latest_completed_scans(db: Session, user: User) -> list[Scan]:
    """The most recent completed scan of each repository the user owns.

    This is the portfolio's *current* state. Summing every scan's report
    instead would count one unfixed vulnerability once per re-scan.
    """
    rows = (
        db.execute(
            select(Scan)
            .join(Repository)
            .where(Repository.user_id == user.id, Scan.status == ScanStatus.COMPLETED)
            .order_by(Scan.created_at.desc())
        )
        .scalars()
        .all()
    )

    seen: set[uuid.UUID] = set()
    latest: list[Scan] = []
    for scan in rows:
        if scan.repository_id in seen:
            continue
        seen.add(scan.repository_id)
        latest.append(scan)
    return latest


def dashboard_summary(db: Session, user: User) -> DashboardSummary:
    """Aggregate the overview page's headline numbers in one round trip."""
    status_rows = db.execute(
        select(Scan.status, Scan.created_at)
        .join(Repository)
        .where(Repository.user_id == user.id)
    ).all()
    connected_repos = (
        db.execute(select(Repository.id).where(Repository.user_id == user.id))
        .scalars()
        .all()
    )

    running = sum(
        1
        for status, _ in status_rows
        if status in (ScanStatus.PENDING, ScanStatus.RUNNING)
    )
    last_scan_at = max((created for _, created in status_rows), default=None)

    latest = latest_completed_scans(db, user)
    counts = finding_counts(db, latest)

    totals = {sev.value: 0 for sev in Severity}
    open_findings = 0
    suppressed = 0
    for summary in counts.values():
        for sev, n in summary.counts_by_severity.items():
            totals[sev] = totals.get(sev, 0) + n
            open_findings += n
        suppressed += summary.suppressed

    return DashboardSummary(
        total_scans=len(status_rows),
        running_scans=running,
        connected_repos=len(connected_repos),
        scanned_repos=len(latest),
        counts_by_severity=totals,
        open_findings=open_findings,
        suppressed_findings=suppressed,
        last_scan_at=last_scan_at,
    )


def get_scan(db: Session, scan_id: uuid.UUID, user: User) -> Optional[Scan]:
    """Fetch a scan only if it belongs to a repository the user owns."""
    return db.execute(
        select(Scan)
        .join(Repository)
        .where(Scan.id == scan_id, Repository.user_id == user.id)
    ).scalar_one_or_none()


# Statuses a scan can still be stopped from.
_CANCELABLE = (ScanStatus.PENDING, ScanStatus.RUNNING)


def cancel_scan(db: Session, scan: Scan) -> bool:
    """Stop an in-flight scan. Returns False if it had already finished.

    Revoking with ``terminate`` kills the worker's Strix subprocess, which is
    the point: an uncancellable run keeps spending against the LLM budget. The
    row is marked canceled regardless of whether the broker acknowledges, so a
    user is never stuck watching a scan they have already stopped.
    """
    if scan.status not in _CANCELABLE:
        return False

    if scan.celery_task_id:
        try:
            celery.control.revoke(
                scan.celery_task_id, terminate=True, signal="SIGTERM"
            )
        except Exception:  # noqa: BLE001 - a dead broker must not block the UI
            logger.warning(
                "Could not revoke task %s for scan %s", scan.celery_task_id, scan.id,
                exc_info=True,
            )

    scan.status = ScanStatus.CANCELED
    scan.completed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(scan)
    return True


def get_finding(db: Session, scan: Scan, vulnerability_id: uuid.UUID):
    """Fetch one finding, scoped to a scan the caller already owns."""
    return db.execute(
        select(Vulnerability).where(
            Vulnerability.id == vulnerability_id, Vulnerability.scan_id == scan.id
        )
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

    # Triage verdicts live per (repo, fingerprint) so they survive re-scans,
    # and the diff marks what this run turned up that the last one didn't.
    triage = triage_service.triage_map(db, scan.repository_id)
    diff = triage_service.diff_against_previous(db, scan)

    findings: list[VulnerabilityRead] = []
    suppressed = 0
    for v in vulns:
        read = VulnerabilityRead.model_validate(v)
        verdict = triage.get(v.fingerprint) if v.fingerprint else None
        if verdict is not None:
            read.triage_status = verdict.status.value
            read.triage_note = verdict.note
            read.github_issue_url = verdict.github_issue_url
            if verdict.status in triage_service.SUPPRESSED_STATUSES:
                suppressed += 1
        read.is_new = bool(v.fingerprint and v.fingerprint in diff.new_fingerprints)
        findings.append(read)

    return ScanReport(
        scan=ScanRead.model_validate(scan),
        total=len(vulns),
        counts_by_severity=counts,
        fixable_count=sum(1 for v in vulns if v.suggested_fix),
        open_count=len(vulns) - suppressed,
        suppressed_count=suppressed,
        diff=ScanDiffRead(
            has_baseline=diff.has_baseline,
            previous_scan_id=diff.previous_scan_id,
            new_count=len(diff.new_fingerprints),
            fixed_count=diff.fixed_count,
            persisting_count=diff.persisting_count,
        ),
        vulnerabilities=findings,
    )
