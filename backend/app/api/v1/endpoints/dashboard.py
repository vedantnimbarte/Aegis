"""Overview endpoints — portfolio-wide aggregates for the dashboard home."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api import deps
from app.api.deps import Principal
from app.db.session import get_db
from app.schemas.scan import CostSummary, DashboardSummary
from app.services import org_service, scan_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(
    all_organizations: bool = False,
    principal: Principal = Depends(deps.require_viewer),
    db: Session = Depends(get_db),
) -> DashboardSummary:
    """Current security posture across the organization's targets.

    Counted from the latest completed scan per target so a vulnerability that
    survives ten re-scans is reported once, not ten times.

    With ``all_organizations=true`` an agency sees every client workspace it
    operates in one view, which is the whole point of having them.
    """
    if all_organizations and principal.user is not None:
        org_ids = org_service.accessible_organization_ids(db, principal.user)
    else:
        org_ids = [principal.organization.id]
    return scan_service.dashboard_summary(db, org_ids)


@router.get("/costs", response_model=CostSummary)
def cost_summary(
    principal: Principal = Depends(deps.require_member),
    db: Session = Depends(get_db),
) -> CostSummary:
    """What testing cost this month, and what it bought.

    Every figure comes from the engine's own usage report, recorded per scan.
    Cost per validated finding is the number that actually compares one
    security tool with another, so it is stated rather than buried.
    """
    return scan_service.cost_summary(db, principal.organization)
