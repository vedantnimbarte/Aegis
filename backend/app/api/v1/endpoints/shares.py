"""Public report links — the one unauthenticated read path in the API.

A share token is a bearer credential for a document that describes how to
attack the customer, so this module is deliberately narrow:

* The token is the only input. No enumeration surface, no organization
  context, no way to reach a second scan from the first.
* Expiry and revocation are checked on every request, not cached.
* Proof-of-concept code and request/response transcripts are withheld unless
  the link was explicitly minted to include them.
* Every response is ``no-store``: a report cached by a corporate proxy on the
  recipient's side outlives the expiry we promised.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.schemas.scan import ScanReport
from app.services import (
    audit_service,
    compliance,
    report_pdf,
    scan_service,
    share_service,
)

router = APIRouter(prefix="/shared", tags=["shared reports"])

_NO_STORE = {"Cache-Control": "no-store, max-age=0", "X-Robots-Tag": "noindex, nofollow"}


def _resolve(db: Session, token: str):
    """The share and its scan, or a 404 that says nothing about which failed."""
    share = share_service.resolve(db, token)
    if share is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail="This link is not valid, or it has expired.",
        )
    return share, share.scan


def _record_view(db: Session, share, scan) -> None:
    share_service.record_view(db, share)
    audit_service.record(
        db,
        organization_id=scan.target.organization_id,
        action=audit_service.SHARE_VIEWED,
        subject_type="scan",
        subject_id=scan.id,
        detail={"label": share.label},
    )


@router.get("/{token}", response_model=ScanReport)
def read_shared_report(
    token: str, response: Response, db: Session = Depends(get_db)
) -> ScanReport:
    """The shared report, minus anything that would function as an exploit."""
    share, scan = _resolve(db, token)
    report = scan_service.render_report(db, scan, include_poc=share.include_poc)
    _record_view(db, share, scan)
    response.headers.update(_NO_STORE)
    return report


@router.get(
    "/{token}/report.pdf",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
def download_shared_report(
    token: str,
    compliance_pack: bool = False,
    db: Session = Depends(get_db),
) -> Response:
    """The shared report as a PDF — the file a reviewer forwards to their team."""
    share, scan = _resolve(db, token)
    report = scan_service.render_report(db, scan, include_poc=share.include_poc)

    org = scan.target.organization
    context = None
    if compliance_pack:
        context = compliance.build_context(
            report,
            organization_name=org.display_brand,
            vendor_name=settings.COMPLIANCE_VENDOR_NAME,
            attestor_name=settings.COMPLIANCE_ATTESTOR_NAME,
            attestor_title=settings.COMPLIANCE_ATTESTOR_TITLE,
        )

    pdf_bytes = report_pdf.build_report_pdf(
        report,
        scan.target.name,
        compliance=context,
        brand=org.brand_name or "AEGIS",
        include_poc=share.include_poc,
    )
    _record_view(db, share, scan)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="aegis-report-{scan.id}.pdf"',
            **_NO_STORE,
        },
    )
