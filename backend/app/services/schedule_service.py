"""Recurring-scan schedule persistence and the scheduler's due-query.

Every lookup joins through Repository so a user only ever sees schedules for
repositories they own (tenant isolation, spec §5).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.repository import Repository
from app.models.schedule import Schedule
from app.models.user import User
from app.schemas.schedule import ScheduleCreate, ScheduleUpdate
from app.services import repo_service, schedule_planner


def _now() -> datetime:
    return datetime.now(timezone.utc)


def list_schedules(db: Session, user: User) -> Sequence[Schedule]:
    return db.execute(
        select(Schedule)
        .join(Repository)
        .where(Repository.user_id == user.id)
        .order_by(Schedule.created_at.desc())
    ).scalars().all()


def get_schedule(db: Session, schedule_id: uuid.UUID, user: User) -> Optional[Schedule]:
    return db.execute(
        select(Schedule)
        .join(Repository)
        .where(Schedule.id == schedule_id, Repository.user_id == user.id)
    ).scalar_one_or_none()


def create_schedule(
    db: Session, user: User, payload: ScheduleCreate
) -> tuple[Optional[Schedule], str]:
    """Create a schedule for a user-owned repo.

    Returns ``(schedule, "")`` on success, or ``(None, code)`` where code is
    ``"repo_not_found"`` or ``"exists"`` (a repo already has a schedule).
    """
    repo = repo_service.get_repository(db, payload.repository_id, user)
    if repo is None:
        return None, "repo_not_found"

    existing = db.execute(
        select(Schedule).where(Schedule.repository_id == repo.id)
    ).scalar_one_or_none()
    if existing is not None:
        return None, "exists"

    schedule = Schedule(
        repository_id=repo.id,
        frequency=payload.frequency,
        scan_mode=payload.scan_mode,
        custom_instructions=payload.custom_instructions,
        next_run_at=schedule_planner.compute_next_run(_now(), payload.frequency.value),
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule, ""


def update_schedule(
    db: Session, schedule: Schedule, payload: ScheduleUpdate
) -> Schedule:
    if payload.frequency is not None:
        schedule.frequency = payload.frequency
        # A cadence change re-bases the next run from now.
        schedule.next_run_at = schedule_planner.compute_next_run(
            _now(), payload.frequency.value
        )
    if payload.scan_mode is not None:
        schedule.scan_mode = payload.scan_mode
    if payload.enabled is not None:
        schedule.enabled = payload.enabled
    if "custom_instructions" in payload.model_fields_set:
        schedule.custom_instructions = payload.custom_instructions

    db.commit()
    db.refresh(schedule)
    return schedule


def delete_schedule(db: Session, schedule: Schedule) -> None:
    db.delete(schedule)
    db.commit()


def due_schedules(db: Session, now: Optional[datetime] = None) -> Sequence[Schedule]:
    """Enabled schedules whose next run is at or before ``now``."""
    moment = now or _now()
    return db.execute(
        select(Schedule).where(
            Schedule.enabled.is_(True), Schedule.next_run_at <= moment
        )
    ).scalars().all()


def advance_after_dispatch(
    db: Session, schedule: Schedule, now: Optional[datetime] = None
) -> None:
    """Stamp the run and move next_run_at forward one interval."""
    moment = now or _now()
    schedule.last_run_at = moment
    schedule.next_run_at = schedule_planner.compute_next_run(
        moment, schedule.frequency.value
    )
    db.commit()
