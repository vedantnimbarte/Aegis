"""Scan endpoints."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api import deps
from app.db.session import get_db
from app.models.user import User
from app.schemas.scan import AutofixResponse, ScanCreate, ScanRead, ScanReport
from app.services import autofix, billing, report_pdf, scan_service

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
