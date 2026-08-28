"""Recurring-scan schedule endpoints (CRUD)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.api.deps import Principal
from app.db.session import get_db
from app.schemas.schedule import ScheduleCreate, ScheduleRead, ScheduleUpdate
from app.services import schedule_service

router = APIRouter(prefix="/schedules", tags=["schedules"])


@router.get("", response_model=list[ScheduleRead])
def list_schedules(
    principal: Principal = Depends(deps.require_viewer),
    db: Session = Depends(get_db),
) -> list[ScheduleRead]:
    """List the organization's recurring scan schedules."""
    return schedule_service.list_schedules(db, principal.organization)


@router.post("", response_model=ScheduleRead, status_code=status.HTTP_201_CREATED)
def create_schedule(
    payload: ScheduleCreate,
    principal: Principal = Depends(deps.require_member),
    db: Session = Depends(get_db),
) -> ScheduleRead:
    """Set up recurring scans for a target (one schedule per target)."""
    schedule, error = schedule_service.create_schedule(
        db, principal.organization, payload
    )
    if error == "target_not_found":
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Target not found")
    if error == "exists":
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="This target already has a schedule",
        )
    return schedule


@router.patch("/{schedule_id}", response_model=ScheduleRead)
def update_schedule(
    schedule_id: uuid.UUID,
    payload: ScheduleUpdate,
    principal: Principal = Depends(deps.require_member),
    db: Session = Depends(get_db),
) -> ScheduleRead:
    """Update a schedule (cadence, mode, instructions, or enabled)."""
    schedule = schedule_service.get_schedule(db, schedule_id, principal.organization)
    if schedule is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Schedule not found")
    return schedule_service.update_schedule(db, schedule, payload)


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule(
    schedule_id: uuid.UUID,
    principal: Principal = Depends(deps.require_member),
    db: Session = Depends(get_db),
):
    """Delete a recurring scan schedule."""
    schedule = schedule_service.get_schedule(db, schedule_id, principal.organization)
    if schedule is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Schedule not found")
    schedule_service.delete_schedule(db, schedule)
