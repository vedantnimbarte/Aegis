"""Overview endpoints — portfolio-wide aggregates for the dashboard home."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api import deps
from app.db.session import get_db
from app.models.user import User
from app.schemas.scan import DashboardSummary
from app.services import scan_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(get_db),
) -> DashboardSummary:
    """Current security posture across every repository the user owns.

    Counted from the latest completed scan per repository so a vulnerability
    that survives ten re-scans is reported once, not ten times.
    """
    return scan_service.dashboard_summary(db, current_user)
