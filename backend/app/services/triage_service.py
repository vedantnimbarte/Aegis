"""Triage verdicts, retest outcomes, and scan-over-scan diffing.

All three live here because they share one idea: a finding's identity is its
``fingerprint``, not its row id (see ``finding_identity``). Triage is stored
per ``(target, fingerprint)`` so it survives re-scans, the diff is a set
comparison of fingerprints between consecutive completed scans, and a retest
verdict attaches to the same key so "we proved this is fixed" outlives the run
that proved it.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import IssueTracker, RetestOutcome, ScanStatus, TriageStatus
from app.models.organization import Organization
from app.models.scan import Scan
from app.models.target import Target
from app.models.triage import FindingTriage
from app.models.vulnerability import Vulnerability

# Verdicts that mean "a human decided this doesn't need action".
SUPPRESSED_STATUSES = frozenset(
    {TriageStatus.FALSE_POSITIVE, TriageStatus.ACCEPTED_RISK, TriageStatus.FIXED}
)


@dataclass(frozen=True)
class ScanDiff:
    """How this scan's findings compare with the previous completed one."""

    previous_scan_id: Optional[uuid.UUID] = None
    new_fingerprints: frozenset[str] = frozenset()
    fixed_count: int = 0
    persisting_count: int = 0

    @property
    def has_baseline(self) -> bool:
        return self.previous_scan_id is not None


def triage_map(db: Session, target_id: uuid.UUID) -> dict[str, FindingTriage]:
    """All triage verdicts for a target, keyed by fingerprint."""
    rows = db.execute(
        select(FindingTriage).where(FindingTriage.target_id == target_id)
    ).scalars().all()
    return {row.fingerprint: row for row in rows}


def get_verdict(
    db: Session, target_id: uuid.UUID, fingerprint: str
) -> Optional[FindingTriage]:
    return db.execute(
        select(FindingTriage).where(
            FindingTriage.target_id == target_id,
            FindingTriage.fingerprint == fingerprint,
        )
    ).scalar_one_or_none()


def _get_or_create(
    db: Session, target_id: uuid.UUID, fingerprint: str
) -> FindingTriage:
    row = get_verdict(db, target_id, fingerprint)
    if row is None:
        row = FindingTriage(target_id=target_id, fingerprint=fingerprint)
        db.add(row)
    return row


def set_triage(
    db: Session,
    *,
    target_id: uuid.UUID,
    fingerprint: str,
    status: TriageStatus,
    note: Optional[str] = None,
) -> FindingTriage:
    """Upsert the verdict for one finding of a target."""
    row = _get_or_create(db, target_id, fingerprint)
    row.status = status
    # An explicit empty string clears the note; None leaves it untouched.
    if note is not None:
        row.note = note or None

    db.commit()
    db.refresh(row)
    return row


def record_issue(
    db: Session,
    *,
    target_id: uuid.UUID,
    fingerprint: str,
    tracker: IssueTracker,
    url: str,
    key: Optional[str] = None,
) -> FindingTriage:
    """Remember where this finding was filed, so a re-scan reuses the ticket."""
    row = _get_or_create(db, target_id, fingerprint)
    row.github_issue_url = url
    row.issue_tracker = tracker
    row.issue_key = key
    db.commit()
    db.refresh(row)
    return row


def record_retest(
    db: Session,
    *,
    target_id: uuid.UUID,
    fingerprint: str,
    outcome: RetestOutcome,
    scan_id: Optional[uuid.UUID] = None,
    evidence: Optional[dict] = None,
) -> FindingTriage:
    """Record what re-running a finding's proof of concept actually showed.

    A ``FIXED`` outcome also sets the triage status, because that is the whole
    point: the verdict is now backed by a re-run exploit rather than someone's
    say-so. Any other outcome deliberately leaves the status alone — a retest
    that could not run is not evidence of anything, and quietly reopening a
    finding a human closed would be the tool overruling its user.
    """
    row = _get_or_create(db, target_id, fingerprint)
    row.retest_outcome = outcome
    row.retested_at = datetime.now(timezone.utc)
    row.last_retest_scan_id = scan_id
    row.retest_evidence = evidence
    if outcome is RetestOutcome.FIXED:
        row.status = TriageStatus.FIXED
    db.commit()
    db.refresh(row)
    return row


def previous_completed_scan(db: Session, scan: Scan) -> Optional[Scan]:
    """The most recent completed full scan of the same target before ``scan``.

    Retests are excluded: a retest looks at one finding, so treating it as the
    baseline would report every *other* finding as newly fixed and then newly
    reintroduced on the following scan.
    """
    from app.models.enums import ScanTrigger

    return db.execute(
        select(Scan)
        .where(
            Scan.target_id == scan.target_id,
            Scan.id != scan.id,
            Scan.status == ScanStatus.COMPLETED,
            Scan.trigger != ScanTrigger.RETEST,
            Scan.created_at < scan.created_at,
        )
        .order_by(Scan.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def _fingerprints_for(db: Session, scan_id: uuid.UUID) -> set[str]:
    rows = db.execute(
        select(Vulnerability.fingerprint).where(Vulnerability.scan_id == scan_id)
    ).scalars().all()
    return {fp for fp in rows if fp}


def diff_against_previous(db: Session, scan: Scan) -> ScanDiff:
    """Compare ``scan``'s findings with the previous completed scan's.

    With no earlier scan to compare against, everything is reported as
    unchanged rather than as new — a first scan is a baseline, not a
    regression.
    """
    previous = previous_completed_scan(db, scan)
    if previous is None:
        return ScanDiff()

    current = _fingerprints_for(db, scan.id)
    before = _fingerprints_for(db, previous.id)

    return ScanDiff(
        previous_scan_id=previous.id,
        new_fingerprints=frozenset(current - before),
        fixed_count=len(before - current),
        persisting_count=len(current & before),
    )


def org_owns_scan(db: Session, scan: Scan, org: Organization) -> bool:
    """Whether ``scan``'s target belongs to ``org``."""
    return db.execute(
        select(Target.id).where(
            Target.id == scan.target_id, Target.organization_id == org.id
        )
    ).scalar_one_or_none() is not None


def suppressed_fingerprints(
    triage: dict[str, FindingTriage], fingerprints: Sequence[str]
) -> set[str]:
    """Subset of ``fingerprints`` a human has marked as not needing action."""
    return {
        fp
        for fp in fingerprints
        if fp in triage and triage[fp].status in SUPPRESSED_STATUSES
    }
