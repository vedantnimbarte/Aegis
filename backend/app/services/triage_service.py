"""Triage verdicts and scan-over-scan diffing.

Both live here because they share one idea: a finding's identity is its
``fingerprint``, not its row id (see ``finding_identity``). Triage is stored
per ``(repository, fingerprint)`` so it survives re-scans, and the diff is a
set comparison of fingerprints between consecutive completed scans.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import ScanStatus, TriageStatus
from app.models.repository import Repository
from app.models.scan import Scan
from app.models.triage import FindingTriage
from app.models.user import User
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


def triage_map(db: Session, repository_id: uuid.UUID) -> dict[str, FindingTriage]:
    """All triage verdicts for a repository, keyed by fingerprint."""
    rows = db.execute(
        select(FindingTriage).where(FindingTriage.repository_id == repository_id)
    ).scalars().all()
    return {row.fingerprint: row for row in rows}


def set_triage(
    db: Session,
    *,
    repository_id: uuid.UUID,
    fingerprint: str,
    status: TriageStatus,
    note: Optional[str] = None,
) -> FindingTriage:
    """Upsert the verdict for one finding of a repository."""
    row = db.execute(
        select(FindingTriage).where(
            FindingTriage.repository_id == repository_id,
            FindingTriage.fingerprint == fingerprint,
        )
    ).scalar_one_or_none()

    if row is None:
        row = FindingTriage(
            repository_id=repository_id, fingerprint=fingerprint, status=status, note=note
        )
        db.add(row)
    else:
        row.status = status
        # An explicit empty string clears the note; None leaves it untouched.
        if note is not None:
            row.note = note or None

    db.commit()
    db.refresh(row)
    return row


def previous_completed_scan(db: Session, scan: Scan) -> Optional[Scan]:
    """The most recent completed scan of the same repo before ``scan``."""
    return db.execute(
        select(Scan)
        .where(
            Scan.repository_id == scan.repository_id,
            Scan.id != scan.id,
            Scan.status == ScanStatus.COMPLETED,
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


def user_owns_scan_repository(db: Session, scan: Scan, user: User) -> bool:
    """Whether ``user`` owns the repository ``scan`` belongs to."""
    return db.execute(
        select(Repository.id).where(
            Repository.id == scan.repository_id, Repository.user_id == user.id
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
