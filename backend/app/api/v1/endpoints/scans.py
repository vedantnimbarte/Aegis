"""Scan endpoints."""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api import deps
from app.core.config import settings
from app.db.session import get_db
from app.models.enums import ScanStatus
from app.models.user import User
from app.schemas.scan import (
    AutofixResponse,
    FindingIssueResponse,
    ScanCreate,
    ScanProgressRead,
    ScanRead,
    ScanReport,
    TriageUpdate,
    VulnerabilityRead,
)
from app.services import (
    autofix,
    billing,
    finding_issue,
    notifications,
    report_pdf,
    sarif,
    scan_progress,
    scan_service,
    triage_service,
)

router = APIRouter(prefix="/scans", tags=["scans"])


@router.get("", response_model=list[ScanRead])
def list_scans(
    repository_id: uuid.UUID | None = None,
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(get_db),
) -> list[ScanRead]:
    """List the user's scans (optionally filtered by repository) — scan history."""
    return scan_service.list_scans(db, current_user, repository_id)


@router.post("", response_model=ScanRead, status_code=status.HTTP_202_ACCEPTED)
def create_scan(
    payload: ScanCreate,
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(get_db),
) -> ScanRead:
    """Trigger a new Strix scan for a user-owned repository."""
    deps.ensure_email_verified(current_user)
    deps.ensure_scan_authorized(current_user)
    try:
        billing.assert_can_create_scan(db, current_user)
    except billing.PaymentRequiredError as exc:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            detail={"message": exc.detail, "reason": exc.reason},
        )

    scan = scan_service.create_scan(
        db,
        user=current_user,
        repository_id=payload.repository_id,
        scan_mode=payload.scan_mode,
        custom_instructions=payload.custom_instructions,
    )
    if scan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Repository not found")
    return scan


@router.get("/{scan_id}", response_model=ScanRead)
def get_scan(
    scan_id: uuid.UUID,
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(get_db),
) -> ScanRead:
    """Return status and metadata for a single scan."""
    scan = scan_service.get_scan(db, scan_id, current_user)
    if scan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Scan not found")
    return scan


@router.get("/{scan_id}/progress", response_model=ScanProgressRead)
def get_scan_progress(
    scan_id: uuid.UUID,
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(get_db),
) -> ScanProgressRead:
    """Live agent progress for a running scan.

    Reads Strix's on-disk run state, which is best-effort by nature: before
    the sandbox is up there is nothing to read, so this returns a `preparing`
    phase with no steps rather than 404-ing.
    """
    scan = scan_service.get_scan(db, scan_id, current_user)
    if scan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Scan not found")

    snapshot = scan_progress.read_progress(
        Path(settings.STRIX_WORK_DIR) / str(scan.id)
    )
    return ScanProgressRead(
        status=scan.status,
        phase=snapshot.phase,
        run_id=snapshot.run_id,
        steps=[vars(step) for step in snapshot.steps],
        agents=snapshot.agents,
        llm_requests=snapshot.llm_requests,
        input_tokens=snapshot.input_tokens,
        output_tokens=snapshot.output_tokens,
        cost_usd=snapshot.cost_usd,
    )


@router.post("/{scan_id}/cancel", response_model=ScanRead)
def cancel_scan(
    scan_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(get_db),
) -> ScanRead:
    """Stop a pending or running scan, terminating its worker task.

    The owner is notified the same way they are for a completed or failed
    scan — a scan that stops without a word looks like a bug. Delivery runs
    after the response so a slow webhook can't hold up the cancel.
    """
    scan = scan_service.get_scan(db, scan_id, current_user)
    if scan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Scan not found")
    if not scan_service.cancel_scan(db, scan):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Scan already {scan.status.value}; nothing to cancel",
        )

    # Read what the notification needs while the session is still open.
    background_tasks.add_task(
        notifications.notify_scan_finished,
        email_to=current_user.email,
        slack_webhook_url=current_user.slack_webhook_url,
        repo_name=scan.repository.name,
        status=ScanStatus.CANCELED.value,
        total=0,
        counts={},
        report_url=f"{settings.DASHBOARD_URL}/scans/{scan.id}",
    )
    return scan


@router.patch(
    "/{scan_id}/findings/{vulnerability_id}/triage", response_model=VulnerabilityRead
)
def triage_finding(
    scan_id: uuid.UUID,
    vulnerability_id: uuid.UUID,
    payload: TriageUpdate,
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(get_db),
) -> VulnerabilityRead:
    """Record a verdict on a finding.

    Stored against the finding's fingerprint rather than this row, so the
    verdict carries forward to every future scan of the same repository.
    """
    scan = scan_service.get_scan(db, scan_id, current_user)
    if scan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Scan not found")

    vulnerability = scan_service.get_finding(db, scan, vulnerability_id)
    if vulnerability is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Finding not found")
    if not vulnerability.fingerprint:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="This finding predates fingerprinting and cannot be triaged",
        )

    verdict = triage_service.set_triage(
        db,
        repository_id=scan.repository_id,
        fingerprint=vulnerability.fingerprint,
        status=payload.status,
        note=payload.note,
    )
    read = VulnerabilityRead.model_validate(vulnerability)
    read.triage_status = verdict.status.value
    read.triage_note = verdict.note
    read.github_issue_url = verdict.github_issue_url
    return read


@router.post(
    "/{scan_id}/findings/{vulnerability_id}/issue", response_model=FindingIssueResponse
)
def create_finding_issue(
    scan_id: uuid.UUID,
    vulnerability_id: uuid.UUID,
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(get_db),
) -> FindingIssueResponse:
    """Open a GitHub issue for a finding in the scanned repository.

    The issue URL is remembered against the finding's fingerprint, so calling
    this again — including from a later scan of the same repo — returns the
    existing issue rather than opening a duplicate.
    """
    deps.ensure_email_verified(current_user)

    scan = scan_service.get_scan(db, scan_id, current_user)
    if scan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Scan not found")

    vulnerability = scan_service.get_finding(db, scan, vulnerability_id)
    if vulnerability is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Finding not found")

    url, error = finding_issue.create_issue(db, scan, vulnerability, current_user)
    if url:
        return FindingIssueResponse(issue_url=url, created=error != "already")

    if error == "no_fingerprint":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="This finding predates fingerprinting and cannot be tracked.",
        )
    if error == "no_installation":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Install the Aegis GitHub App on this repository's "
                "owner to create issues.",
                "reason": "no_installation",
            },
        )
    raise HTTPException(
        status.HTTP_502_BAD_GATEWAY,
        detail="Could not create the issue. Check the GitHub App installation.",
    )


@router.get("/{scan_id}/report", response_model=ScanReport)
def get_scan_report(
    scan_id: uuid.UUID,
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(get_db),
) -> ScanReport:
    """Return the detailed vulnerability report (grouped by severity)."""
    report = scan_service.build_report(db, scan_id, current_user)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Scan not found")
    return report


@router.get(
    "/{scan_id}/report.pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
def export_scan_report_pdf(
    scan_id: uuid.UUID,
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(get_db),
) -> Response:
    """Export the detailed report as a downloadable PDF (compliance/sharing)."""
    scan = scan_service.get_scan(db, scan_id, current_user)
    report = scan_service.build_report(db, scan_id, current_user)
    if scan is None or report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Scan not found")

    pdf_bytes = report_pdf.build_report_pdf(report, scan.repository.name)
    filename = f"aegis-report-{scan_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{scan_id}/report.sarif")
def export_scan_report_sarif(
    scan_id: uuid.UUID,
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(get_db),
) -> Response:
    """Export the report as SARIF 2.1.0 for GitHub code scanning.

    Uploading this to GitHub puts the findings in the repository's Security
    tab. Triage carries over: anything dismissed in Aegis is emitted as a
    SARIF suppression so GitHub doesn't re-raise it.
    """
    scan = scan_service.get_scan(db, scan_id, current_user)
    report = scan_service.build_report(db, scan_id, current_user)
    if scan is None or report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Scan not found")

    document = sarif.build_sarif(report, scan.repository.name)
    filename = f"aegis-report-{scan_id}.sarif"
    return Response(
        content=json.dumps(document, indent=2),
        media_type="application/sarif+json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.post("/{scan_id}/autofix", response_model=AutofixResponse)
def generate_autofix_pr(
    scan_id: uuid.UUID,
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(get_db),
) -> AutofixResponse:
    """Open a GitHub PR applying Strix's suggested fixes for the scan."""
    deps.ensure_email_verified(current_user)
    if not current_user.has_active_subscription:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "message": "An active subscription is required for auto-fix.",
                "reason": "no_subscription",
            },
        )

    scan = scan_service.get_scan(db, scan_id, current_user)
    if scan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Scan not found")

    pr_url, error = autofix.generate_fix_pr(db, scan, current_user)
    if pr_url:
        return AutofixResponse(pull_request_url=pr_url)

    if error == "no_fixes":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="No auto-fixable findings for this scan.",
        )
    if error == "no_installation":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={
                "message": "Install the Aegis GitHub App on this repository's "
                "owner to enable auto-fix.",
                "reason": "no_installation",
            },
        )
    raise HTTPException(
        status.HTTP_502_BAD_GATEWAY,
        detail="Could not open the pull request. Check the GitHub App installation.",
    )
