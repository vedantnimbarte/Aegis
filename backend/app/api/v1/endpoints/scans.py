"""Scan endpoints."""
from __future__ import annotations

import json
import uuid
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api import deps
from app.api.deps import Principal
from app.core.config import settings
from app.db.session import get_db
from app.models.enums import ScanStatus, ScanTrigger, TargetKind
from app.schemas.scan import (
    AutofixResponse,
    FindingIssueRequest,
    FindingIssueResponse,
    RetestResponse,
    ScanCreate,
    ScanProgressRead,
    ScanRead,
    ScanReport,
    ShareCreate,
    ShareCreated,
    ShareRead,
    TriageUpdate,
    VulnerabilityRead,
)
from app.services import (
    audit_service,
    autofix,
    billing,
    billing_plans,
    compliance,
    finding_issue,
    notifications,
    report_pdf,
    sarif,
    scan_progress,
    scan_service,
    share_service,
    triage_service,
)

router = APIRouter(prefix="/scans", tags=["scans"])


def _owned_scan(db: Session, scan_id: uuid.UUID, principal: Principal):
    scan = scan_service.get_scan(db, scan_id, principal.organization)
    if scan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Scan not found")
    return scan


def _brand(principal: Principal, db: Session) -> str:
    """The wordmark on an exported report — white-labelled where allowed."""
    org = principal.organization
    if not org.brand_name:
        return "AEGIS"
    payer = deps.billing_user_for(db, principal)
    if billing_plans.limits_for(payer.subscription_tier).white_label:
        return org.brand_name
    return "AEGIS"


@router.get("", response_model=list[ScanRead])
def list_scans(
    target_id: uuid.UUID | None = None,
    principal: Principal = Depends(deps.require_viewer),
    db: Session = Depends(get_db),
) -> list[ScanRead]:
    """Scan history for the organization (optionally filtered by target)."""
    return scan_service.list_scans(db, principal.organization, target_id)


@router.post("", response_model=ScanRead, status_code=status.HTTP_202_ACCEPTED)
def create_scan(
    payload: ScanCreate,
    principal: Principal = Depends(deps.require_member),
    db: Session = Depends(get_db),
) -> ScanRead:
    """Trigger a new Strix scan against a target the organization owns."""
    deps.ensure_can_scan(principal, db)
    try:
        billing.assert_can_create_scan(
            db, principal.organization, scan_mode=payload.scan_mode
        )
    except billing.PaymentRequiredError as exc:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            detail={"message": exc.detail, "reason": exc.reason},
        )

    scan = scan_service.create_scan(
        db,
        org=principal.organization,
        actor=principal.user,
        target_id=payload.target_id,
        scan_mode=payload.scan_mode,
        custom_instructions=payload.custom_instructions,
    )
    if scan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Target not found")

    audit_service.record(
        db,
        organization_id=principal.organization.id,
        action=audit_service.SCAN_CREATED,
        actor=principal.user,
        subject_type="scan",
        subject_id=scan.id,
        detail={
            "target_id": str(payload.target_id),
            "scan_mode": payload.scan_mode.value,
            "credits": billing_plans.credits_for_mode(payload.scan_mode),
            "via_token": principal.via_token,
        },
    )
    return scan_service.read_scan(scan)


@router.get("/{scan_id}", response_model=ScanRead)
def get_scan(
    scan_id: uuid.UUID,
    principal: Principal = Depends(deps.require_viewer),
    db: Session = Depends(get_db),
) -> ScanRead:
    """Return status and metadata for a single scan."""
    return scan_service.read_scan(_owned_scan(db, scan_id, principal))


@router.get("/{scan_id}/progress", response_model=ScanProgressRead)
def get_scan_progress(
    scan_id: uuid.UUID,
    principal: Principal = Depends(deps.require_viewer),
    db: Session = Depends(get_db),
) -> ScanProgressRead:
    """Live agent progress for a running scan.

    Reads Strix's on-disk run state, which is best-effort by nature: before
    the sandbox is up there is nothing to read, so this returns a `preparing`
    phase with no steps rather than 404-ing.
    """
    scan = _owned_scan(db, scan_id, principal)
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
    principal: Principal = Depends(deps.require_member),
    db: Session = Depends(get_db),
) -> ScanRead:
    """Stop a pending or running scan, terminating its worker task.

    The owner is notified the same way they are for a completed or failed
    scan — a scan that stops without a word looks like a bug. Delivery runs
    after the response so a slow webhook can't hold up the cancel.
    """
    scan = _owned_scan(db, scan_id, principal)
    if not scan_service.cancel_scan(db, scan):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=f"Scan already {scan.status.value}; nothing to cancel",
        )

    payer = deps.billing_user_for(db, principal)
    background_tasks.add_task(
        notifications.notify_scan_finished,
        email_to=payer.email,
        slack_webhook_url=payer.slack_webhook_url,
        repo_name=scan.target.name,
        status=ScanStatus.CANCELED.value,
        total=0,
        counts={},
        report_url=f"{settings.DASHBOARD_URL}/scans/{scan.id}",
    )
    audit_service.record(
        db,
        organization_id=principal.organization.id,
        action=audit_service.SCAN_CANCELED,
        actor=principal.user,
        subject_type="scan",
        subject_id=scan.id,
    )
    return scan_service.read_scan(scan)


@router.patch(
    "/{scan_id}/findings/{vulnerability_id}/triage", response_model=VulnerabilityRead
)
def triage_finding(
    scan_id: uuid.UUID,
    vulnerability_id: uuid.UUID,
    payload: TriageUpdate,
    principal: Principal = Depends(deps.require_member),
    db: Session = Depends(get_db),
) -> VulnerabilityRead:
    """Record a verdict on a finding.

    Stored against the finding's fingerprint rather than this row, so the
    verdict carries forward to every future scan of the same target.
    """
    scan = _owned_scan(db, scan_id, principal)
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
        target_id=scan.target_id,
        fingerprint=vulnerability.fingerprint,
        status=payload.status,
        note=payload.note,
    )
    audit_service.record(
        db,
        organization_id=principal.organization.id,
        action=audit_service.FINDING_TRIAGED,
        actor=principal.user,
        subject_type="finding",
        subject_id=vulnerability.fingerprint,
        detail={"status": payload.status.value, "title": vulnerability.title},
    )
    read = VulnerabilityRead.model_validate(vulnerability)
    read.triage_status = verdict.status.value
    read.triage_note = verdict.note
    read.github_issue_url = verdict.github_issue_url
    read.issue_tracker = verdict.issue_tracker
    read.issue_key = verdict.issue_key
    read.retest_outcome = verdict.retest_outcome
    read.retested_at = verdict.retested_at
    return read


@router.post(
    "/{scan_id}/findings/{vulnerability_id}/retest",
    response_model=RetestResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def retest_finding(
    scan_id: uuid.UUID,
    vulnerability_id: uuid.UUID,
    principal: Principal = Depends(deps.require_member),
    db: Session = Depends(get_db),
) -> RetestResponse:
    """Re-run this finding's proof of concept to see whether it still works.

    The answer is recorded against the finding, not the run, so "verified
    fixed" survives the next full scan. A retest costs no scan credits:
    charging for verification would discourage the step that makes a fixed
    verdict worth anything.
    """
    deps.ensure_can_scan(principal, db)
    scan = _owned_scan(db, scan_id, principal)
    vulnerability = scan_service.get_finding(db, scan, vulnerability_id)
    if vulnerability is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Finding not found")
    if not vulnerability.fingerprint:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="This finding predates fingerprinting and cannot be retested",
        )

    target = scan.target
    # A source-only target has nothing to re-exploit: re-reading the same code
    # proves the fix looks right, which is exactly the claim retesting exists
    # to replace. Ask for a live URL instead of quietly downgrading the answer.
    if target.kind is TargetKind.REPO and not target.live_url:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={
                "message": (
                    "Retesting re-runs the exploit against a running target. Add "
                    "a live URL to this target (or configure authenticated "
                    "testing) to verify fixes."
                ),
                "reason": "no_live_target",
            },
        )

    try:
        billing.assert_can_create_scan(
            db, principal.organization, scan_mode=scan.scan_mode, is_retest=True
        )
    except billing.PaymentRequiredError as exc:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            detail={"message": exc.detail, "reason": exc.reason},
        )

    retest = scan_service.create_scan(
        db,
        org=principal.organization,
        actor=principal.user,
        target_id=scan.target_id,
        scan_mode=scan.scan_mode,
        trigger=ScanTrigger.RETEST,
        retest_fingerprint=vulnerability.fingerprint,
        github_commit_sha=scan.github_commit_sha,
    )
    if retest is None:  # pragma: no cover - the target was just resolved
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Target not found")

    audit_service.record(
        db,
        organization_id=principal.organization.id,
        action=audit_service.RETEST_REQUESTED,
        actor=principal.user,
        subject_type="finding",
        subject_id=vulnerability.fingerprint,
        detail={"scan_id": str(retest.id), "title": vulnerability.title},
    )
    return RetestResponse(
        scan_id=retest.id,
        fingerprint=vulnerability.fingerprint,
        status=retest.status,
    )


@router.post(
    "/{scan_id}/findings/{vulnerability_id}/issue", response_model=FindingIssueResponse
)
def create_finding_issue(
    scan_id: uuid.UUID,
    vulnerability_id: uuid.UUID,
    payload: FindingIssueRequest | None = None,
    principal: Principal = Depends(deps.require_member),
    db: Session = Depends(get_db),
) -> FindingIssueResponse:
    """File a finding in GitHub, Jira, or Linear.

    The issue URL is remembered against the finding's fingerprint, so calling
    this again — including from a later scan of the same target — returns the
    existing ticket rather than opening a duplicate.
    """
    scan = _owned_scan(db, scan_id, principal)
    vulnerability = scan_service.get_finding(db, scan, vulnerability_id)
    if vulnerability is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Finding not found")

    payer = deps.billing_user_for(db, principal)
    url, tracker, key, error = finding_issue.create_issue(
        db,
        scan,
        vulnerability,
        payer,
        tracker=payload.tracker if payload else None,
    )
    if url:
        if error != "already":
            audit_service.record(
                db,
                organization_id=principal.organization.id,
                action=audit_service.FINDING_FILED,
                actor=principal.user,
                subject_type="finding",
                subject_id=vulnerability.fingerprint,
                detail={"tracker": tracker.value, "url": url},
            )
        return FindingIssueResponse(
            issue_url=url, tracker=tracker, issue_key=key, created=error != "already"
        )

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
                "owner, or configure Jira or Linear, to file issues.",
                "reason": "no_installation",
            },
        )
    raise HTTPException(
        status.HTTP_502_BAD_GATEWAY,
        detail=f"Could not file the issue in {tracker.value}. Check the integration settings.",
    )


@router.get("/{scan_id}/report", response_model=ScanReport)
def get_scan_report(
    scan_id: uuid.UUID,
    principal: Principal = Depends(deps.require_viewer),
    db: Session = Depends(get_db),
) -> ScanReport:
    """Return the detailed vulnerability report (grouped by severity)."""
    report = scan_service.build_report(db, scan_id, principal.organization)
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
    compliance_pack: bool = False,
    principal: Principal = Depends(deps.require_viewer),
    db: Session = Depends(get_db),
) -> Response:
    """Export the report as a PDF.

    With ``compliance_pack=true`` it becomes the document an auditor expects:
    executive summary, scope, methodology, control mappings, stated
    limitations, and a signed attestation letter around the same findings.
    """
    scan = _owned_scan(db, scan_id, principal)
    report = scan_service.render_report(db, scan)

    context = None
    if compliance_pack:
        payer = deps.billing_user_for(db, principal)
        if not billing_plans.limits_for(payer.subscription_tier).compliance_reports:
            raise HTTPException(
                status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "message": "Compliance reports are available on Pro and above.",
                    "reason": "plan_feature",
                },
            )
        context = compliance.build_context(
            report,
            organization_name=principal.organization.display_brand,
            vendor_name=settings.COMPLIANCE_VENDOR_NAME,
            attestor_name=settings.COMPLIANCE_ATTESTOR_NAME,
            attestor_title=settings.COMPLIANCE_ATTESTOR_TITLE,
        )

    pdf_bytes = report_pdf.build_report_pdf(
        report,
        scan.target.name,
        compliance=context,
        brand=_brand(principal, db),
    )
    suffix = "compliance-" if compliance_pack else ""
    filename = f"aegis-{suffix}report-{scan_id}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{scan_id}/report.sarif")
def export_scan_report_sarif(
    scan_id: uuid.UUID,
    principal: Principal = Depends(deps.require_viewer),
    db: Session = Depends(get_db),
) -> Response:
    """Export the report as SARIF 2.1.0 for GitHub code scanning.

    Uploading this to GitHub puts the findings in the repository's Security
    tab. Triage carries over: anything dismissed in Aegis is emitted as a
    SARIF suppression so GitHub doesn't re-raise it.
    """
    scan = _owned_scan(db, scan_id, principal)
    report = scan_service.render_report(db, scan)

    document = sarif.build_sarif(report, scan.target.name)
    filename = f"aegis-report-{scan_id}.sarif"
    return Response(
        content=json.dumps(document, indent=2),
        media_type="application/sarif+json",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# --- Share links ----------------------------------------------------------
@router.get("/{scan_id}/shares", response_model=list[ShareRead])
def list_shares(
    scan_id: uuid.UUID,
    principal: Principal = Depends(deps.require_member),
    db: Session = Depends(get_db),
) -> list[ShareRead]:
    scan = _owned_scan(db, scan_id, principal)
    return [ShareRead.model_validate(s) for s in share_service.list_shares(db, scan)]


@router.post(
    "/{scan_id}/shares", response_model=ShareCreated, status_code=status.HTTP_201_CREATED
)
def create_share(
    scan_id: uuid.UUID,
    payload: ShareCreate,
    principal: Principal = Depends(deps.require_member),
    db: Session = Depends(get_db),
) -> ShareCreated:
    """Mint an expiring public link to this report.

    For handing a report to a prospect's security reviewer or an auditor
    without creating them an account. The link always expires, and by default
    withholds proof-of-concept exploit code.
    """
    scan = _owned_scan(db, scan_id, principal)
    share, token = share_service.create_share(
        db,
        scan=scan,
        creator=principal.user,
        label=payload.label,
        expires_in_days=payload.expires_in_days,
        include_poc=payload.include_poc,
    )
    audit_service.record(
        db,
        organization_id=principal.organization.id,
        action=audit_service.SHARE_CREATED,
        actor=principal.user,
        subject_type="scan",
        subject_id=scan.id,
        detail={
            "label": share.label,
            "expires_at": share.expires_at.isoformat(),
            "include_poc": share.include_poc,
        },
    )
    read = ShareRead.model_validate(share)
    return ShareCreated(**read.model_dump(), url=share_service.share_url(token))


@router.delete(
    "/{scan_id}/shares/{share_id}", status_code=status.HTTP_204_NO_CONTENT
)
def revoke_share(
    scan_id: uuid.UUID,
    share_id: uuid.UUID,
    principal: Principal = Depends(deps.require_member),
    db: Session = Depends(get_db),
):
    scan = _owned_scan(db, scan_id, principal)
    share = share_service.get_share(db, scan, share_id)
    if share is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Share link not found")
    share_service.revoke(db, share)
    audit_service.record(
        db,
        organization_id=principal.organization.id,
        action=audit_service.SHARE_REVOKED,
        actor=principal.user,
        subject_type="scan",
        subject_id=scan.id,
        detail={"label": share.label},
    )


@router.post("/{scan_id}/autofix", response_model=AutofixResponse)
def generate_autofix_pr(
    scan_id: uuid.UUID,
    principal: Principal = Depends(deps.require_member),
    db: Session = Depends(get_db),
) -> AutofixResponse:
    """Open a GitHub PR applying Strix's suggested fixes for the scan."""
    payer = deps.billing_user_for(db, principal)
    if principal.user is not None:
        deps.ensure_email_verified(principal.user)
    if not payer.has_active_subscription:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "message": "An active subscription is required for auto-fix.",
                "reason": "no_subscription",
            },
        )

    scan = _owned_scan(db, scan_id, principal)
    pr_url, error = autofix.generate_fix_pr(db, scan, payer)
    if pr_url:
        if error != "already":
            audit_service.record(
                db,
                organization_id=principal.organization.id,
                action=audit_service.AUTOFIX_OPENED,
                actor=principal.user,
                subject_type="scan",
                subject_id=scan.id,
                detail={"pull_request_url": pr_url},
            )
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
