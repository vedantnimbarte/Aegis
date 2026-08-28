"""Scan lifecycle helpers: create/dispatch, list, fetch, and report building.

Every read joins through Target so a caller can only ever see scans belonging
to a target their organization owns (tenant isolation, spec §5 — now enforced
at the organization rather than the user).
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Iterable, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import (
    RetestOutcome,
    ScanMode,
    ScanStatus,
    ScanTrigger,
    Severity,
)
from app.models.organization import Organization
from app.models.scan import Scan
from app.models.target import Target
from app.models.triage import FindingTriage
from app.models.user import User
from app.models.vulnerability import Vulnerability
from app.schemas.scan import (
    AttackChainRead,
    CostSummary,
    DashboardSummary,
    EvidenceRead,
    ScanDiffRead,
    ScanRead,
    ScanReport,
    TargetCostRead,
    VulnerabilityRead,
)
from app.services import attack_paths, target_service, triage_service
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
    org: Organization,
    actor: Optional[User],
    target_id: uuid.UUID,
    scan_mode: ScanMode,
    custom_instructions: Optional[str] = None,
    trigger: ScanTrigger = ScanTrigger.MANUAL,
    github_installation_id: Optional[str] = None,
    github_pr_number: Optional[int] = None,
    github_commit_sha: Optional[str] = None,
    retest_fingerprint: Optional[str] = None,
) -> Optional[Scan]:
    """Create a `pending` scan for an org-owned target and enqueue the job.

    Returns None if the target does not exist or is not owned by the
    organization (the endpoint maps that to 404, avoiding an existence oracle).
    """
    target = target_service.get_target(db, target_id, org)
    if target is None:
        return None

    scan = Scan(
        target_id=target.id,
        created_by_user_id=actor.id if actor is not None else None,
        scan_mode=scan_mode,
        custom_instructions=custom_instructions,
        trigger=trigger,
        github_installation_id=github_installation_id,
        github_pr_number=github_pr_number,
        github_commit_sha=github_commit_sha,
        retest_fingerprint=retest_fingerprint,
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
    verified_fixed: int = 0


def summarize_findings(
    rows: Iterable[tuple[uuid.UUID, uuid.UUID, Severity, Optional[str]]],
    suppressed_keys: frozenset[tuple[uuid.UUID, Optional[str]]],
    verified_keys: frozenset[tuple[uuid.UUID, Optional[str]]] = frozenset(),
) -> dict[uuid.UUID, FindingCounts]:
    """Group ``(scan_id, target_id, severity, fingerprint)`` rows per scan.

    ``counts_by_severity`` deliberately excludes findings a human has triaged
    away, so a list row shows what is still outstanding rather than what was
    once reported; ``total`` counts everything, so the difference is what was
    triaged away. ``verified_fixed`` counts the subset proven fixed by a
    retest — the number worth putting on a pricing page. Pure, so it can be
    exercised without a database.
    """
    out: dict[uuid.UUID, FindingCounts] = {}
    for scan_id, target_id, severity, fingerprint in rows:
        summary = out.setdefault(scan_id, FindingCounts())
        summary.total += 1
        key = (target_id, fingerprint)
        if key in suppressed_keys:
            summary.suppressed += 1
            if key in verified_keys:
                summary.verified_fixed += 1
        else:
            sev = severity.value if isinstance(severity, Severity) else str(severity)
            summary.counts_by_severity[sev] = summary.counts_by_severity.get(sev, 0) + 1
    return out


def _triage_keys(
    db: Session, target_ids: Sequence[uuid.UUID]
) -> tuple[
    frozenset[tuple[uuid.UUID, Optional[str]]],
    frozenset[tuple[uuid.UUID, Optional[str]]],
]:
    """``(suppressed, verified_fixed)`` ``(target_id, fingerprint)`` pairs."""
    if not target_ids:
        return frozenset(), frozenset()
    rows = db.execute(
        select(
            FindingTriage.target_id,
            FindingTriage.fingerprint,
            FindingTriage.status,
            FindingTriage.retest_outcome,
        ).where(FindingTriage.target_id.in_(target_ids))
    ).all()

    suppressed = {
        (target_id, fp)
        for target_id, fp, status, _ in rows
        if status in triage_service.SUPPRESSED_STATUSES
    }
    verified = {
        (target_id, fp)
        for target_id, fp, _, outcome in rows
        if outcome is RetestOutcome.FIXED
    }
    return frozenset(suppressed), frozenset(verified)


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
            Scan.target_id,
            Vulnerability.severity,
            Vulnerability.fingerprint,
        )
        .join(Scan, Scan.id == Vulnerability.scan_id)
        .where(Vulnerability.scan_id.in_(scan_ids))
    ).all()

    suppressed, verified = _triage_keys(db, list({s.target_id for s in scans}))
    counts = summarize_findings(rows, suppressed, verified)
    # A scan with no findings still gets a zeroed summary, so the UI can tell
    # "clean" apart from "not computed".
    for scan in scans:
        counts.setdefault(scan.id, FindingCounts())
    return counts


def read_scan(scan: Scan) -> ScanRead:
    """A scan row plus its target's name and kind, so a list needs one call."""
    read = ScanRead.model_validate(scan)
    target = scan.target
    if target is not None:
        read.target_name = target.name
        read.target_kind = target.kind
    return read


def list_scans(
    db: Session, org: Organization, target_id: Optional[uuid.UUID] = None
) -> list[ScanRead]:
    """Scan history, newest first, each row carrying its finding summary."""
    stmt = select(Scan).join(Target).where(Target.organization_id == org.id)
    if target_id is not None:
        stmt = stmt.where(Scan.target_id == target_id)
    stmt = stmt.order_by(Scan.created_at.desc())
    scans = list(db.execute(stmt).scalars().all())

    counts = finding_counts(db, scans)
    out: list[ScanRead] = []
    for scan in scans:
        read = read_scan(scan)
        # Only a finished scan has a meaningful count; leaving it null while a
        # scan runs stops the UI rendering a premature "0 findings".
        if scan.status is ScanStatus.COMPLETED:
            summary = counts[scan.id]
            read.counts_by_severity = summary.counts_by_severity
            read.findings_total = summary.total
        out.append(read)
    return out


def latest_completed_scans(
    db: Session, organization_ids: Sequence[uuid.UUID]
) -> list[Scan]:
    """The most recent completed scan of each target across ``organization_ids``.

    This is the portfolio's *current* state. Summing every scan's report
    instead would count one unfixed vulnerability once per re-scan. Retests
    are excluded because they only ever look at a single finding.
    """
    if not organization_ids:
        return []
    rows = (
        db.execute(
            select(Scan)
            .join(Target)
            .where(
                Target.organization_id.in_(organization_ids),
                Scan.status == ScanStatus.COMPLETED,
                Scan.trigger != ScanTrigger.RETEST,
            )
            .order_by(Scan.created_at.desc())
        )
        .scalars()
        .all()
    )

    seen: set[uuid.UUID] = set()
    latest: list[Scan] = []
    for scan in rows:
        if scan.target_id in seen:
            continue
        seen.add(scan.target_id)
        latest.append(scan)
    return latest


def dashboard_summary(
    db: Session, organization_ids: Sequence[uuid.UUID]
) -> DashboardSummary:
    """Aggregate the overview page's headline numbers in one round trip."""
    if not organization_ids:
        return DashboardSummary()

    status_rows = db.execute(
        select(Scan.status, Scan.created_at)
        .join(Target)
        .where(Target.organization_id.in_(organization_ids))
    ).all()
    connected = (
        db.execute(
            select(Target.id).where(Target.organization_id.in_(organization_ids))
        )
        .scalars()
        .all()
    )

    running = sum(
        1
        for status, _ in status_rows
        if status in (ScanStatus.PENDING, ScanStatus.RUNNING)
    )
    last_scan_at = max((created for _, created in status_rows), default=None)

    latest = latest_completed_scans(db, organization_ids)
    counts = finding_counts(db, latest)

    totals = {sev.value: 0 for sev in Severity}
    open_findings = 0
    suppressed = 0
    verified = 0
    for summary in counts.values():
        for sev, n in summary.counts_by_severity.items():
            totals[sev] = totals.get(sev, 0) + n
            open_findings += n
        suppressed += summary.suppressed
        verified += summary.verified_fixed

    return DashboardSummary(
        total_scans=len(status_rows),
        running_scans=running,
        connected_targets=len(connected),
        scanned_targets=len(latest),
        counts_by_severity=totals,
        open_findings=open_findings,
        suppressed_findings=suppressed,
        verified_fixed=verified,
        last_scan_at=last_scan_at,
    )


def get_scan(db: Session, scan_id: uuid.UUID, org: Organization) -> Optional[Scan]:
    """Fetch a scan only if it belongs to a target the organization owns."""
    return db.execute(
        select(Scan)
        .join(Target)
        .where(Scan.id == scan_id, Target.organization_id == org.id)
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


def find_latest_finding(
    db: Session, target_id: uuid.UUID, fingerprint: str
) -> Optional[Vulnerability]:
    """The most recent report of one finding on a target.

    A retest needs the proof of concept, and the newest run has the freshest
    version of it.
    """
    return db.execute(
        select(Vulnerability)
        .join(Scan, Scan.id == Vulnerability.scan_id)
        .where(Scan.target_id == target_id, Vulnerability.fingerprint == fingerprint)
        .order_by(Scan.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()


def build_report(
    db: Session, scan_id: uuid.UUID, org: Organization
) -> Optional[ScanReport]:
    scan = get_scan(db, scan_id, org)
    if scan is None:
        return None
    return render_report(db, scan)


def render_report(db: Session, scan: Scan, include_poc: bool = True) -> ScanReport:
    """Build the report for a scan the caller has already been authorized for.

    ``include_poc=False`` strips working exploit code, which is what a shared
    link hands to someone outside the company.
    """
    vulns = list(
        db.execute(
            select(Vulnerability).where(Vulnerability.scan_id == scan.id)
        ).scalars().all()
    )
    vulns.sort(key=lambda v: _SEVERITY_RANK.get(v.severity, 99))

    counts = {sev.value: 0 for sev in Severity}
    for v in vulns:
        counts[v.severity.value] += 1

    # Triage verdicts live per (target, fingerprint) so they survive re-scans,
    # and the diff marks what this run turned up that the last one didn't.
    triage = triage_service.triage_map(db, scan.target_id)
    diff = triage_service.diff_against_previous(db, scan)

    findings: list[VulnerabilityRead] = []
    suppressed = 0
    verified_fixed = 0
    for v in vulns:
        read = VulnerabilityRead.model_validate(v)
        if not include_poc:
            read.poc_code = None
        read.evidence = _evidence_read(v.evidence, include_poc)
        verdict = triage.get(v.fingerprint) if v.fingerprint else None
        if verdict is not None:
            read.triage_status = verdict.status.value
            read.triage_note = verdict.note
            read.github_issue_url = verdict.github_issue_url
            read.issue_tracker = verdict.issue_tracker
            read.issue_key = verdict.issue_key
            read.retest_outcome = verdict.retest_outcome
            read.retested_at = verdict.retested_at
            if verdict.status in triage_service.SUPPRESSED_STATUSES:
                suppressed += 1
            if verdict.retest_outcome is RetestOutcome.FIXED:
                verified_fixed += 1
        read.is_new = bool(v.fingerprint and v.fingerprint in diff.new_fingerprints)
        findings.append(read)

    return ScanReport(
        scan=read_scan(scan),
        total=len(vulns),
        counts_by_severity=counts,
        fixable_count=sum(1 for v in vulns if v.suggested_fix),
        open_count=len(vulns) - suppressed,
        suppressed_count=suppressed,
        verified_fixed_count=verified_fixed,
        diff=ScanDiffRead(
            has_baseline=diff.has_baseline,
            previous_scan_id=diff.previous_scan_id,
            new_count=len(diff.new_fingerprints),
            fixed_count=diff.fixed_count,
            persisting_count=diff.persisting_count,
        ),
        attack_chains=[
            AttackChainRead(**chain)
            for chain in attack_paths.deserialize(scan.attack_chains)
        ],
        vulnerabilities=findings,
    )


def _evidence_read(raw: Optional[dict], include_poc: bool) -> Optional[EvidenceRead]:
    """Shape a stored evidence bundle for the API.

    On a shared link the transcript goes with the PoC: a request/response pair
    for a live exploit is a working recipe, whatever the button was labelled.
    """
    if not raw:
        return None
    if not include_poc:
        raw = {
            k: v
            for k, v in raw.items()
            if k not in ("request", "response", "poc_output")
        }
        if not raw:
            return None
    return EvidenceRead(**{k: v for k, v in raw.items() if k in EvidenceRead.model_fields})


# --- Cost reporting -------------------------------------------------------
def _period_start() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def cost_summary(db: Session, org: Organization) -> CostSummary:
    """What testing cost this month, and what it bought.

    Every number here comes from ``scans.cost_usd``, which the worker already
    records from the engine's own usage report. Showing it is a choice: buyers
    of a metered product are quietly worried about the bill, and no competitor
    at this price point tells them.
    """
    start = _period_start()
    scans = list(
        db.execute(
            select(Scan)
            .join(Target)
            .where(Target.organization_id == org.id, Scan.created_at >= start)
        )
        .scalars()
        .all()
    )
    counts = finding_counts(db, [s for s in scans if s.status is ScanStatus.COMPLETED])

    per_target: dict[uuid.UUID, TargetCostRead] = {}
    total_cost = 0.0
    total_findings = 0
    validated = 0
    by_mode: dict[str, list[float]] = {}

    for scan in scans:
        cost = scan.cost_usd or 0.0
        total_cost += cost
        if cost:
            by_mode.setdefault(scan.scan_mode.value, []).append(cost)

        row = per_target.setdefault(
            scan.target_id,
            TargetCostRead(
                target_id=scan.target_id,
                target_name=scan.target.name if scan.target else "(deleted)",
                scans=0,
            ),
        )
        row.scans += 1
        row.cost_usd = round(row.cost_usd + cost, 4)

        summary = counts.get(scan.id)
        if summary is not None:
            open_now = sum(summary.counts_by_severity.values())
            row.findings += summary.total
            row.validated_findings += open_now
            total_findings += summary.total
            validated += open_now

    for row in per_target.values():
        row.cost_usd = round(row.cost_usd, 4)
        row.cost_per_validated_finding = (
            round(row.cost_usd / row.validated_findings, 4)
            if row.validated_findings
            else None
        )

    return CostSummary(
        period_start=start,
        total_cost_usd=round(total_cost, 4),
        total_scans=len(scans),
        total_findings=total_findings,
        validated_findings=validated,
        cost_per_scan=round(total_cost / len(scans), 4) if scans else None,
        cost_per_validated_finding=(
            round(total_cost / validated, 4) if validated else None
        ),
        by_target=sorted(
            per_target.values(), key=lambda r: r.cost_usd, reverse=True
        ),
        # A forecast from this organization's own runs beats a generic price
        # list: the same depth costs wildly different amounts on a small
        # service and on a monorepo.
        forecast_by_mode={
            mode: round(sum(values) / len(values), 4)
            for mode, values in by_mode.items()
            if values
        },
    )
