"""Scan endpoints."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.db.session import get_db
from app.models.user import User
from app.schemas.scan import ScanCreate, ScanRead, ScanReport
from app.services import scan_service

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
