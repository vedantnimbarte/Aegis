"""Recurring-scan schedule request/response schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import ScanFrequency, ScanMode


class ScheduleCreate(BaseModel):
    """Set up recurring scans for a repository."""

    repository_id: uuid.UUID
    frequency: ScanFrequency = ScanFrequency.WEEKLY
    scan_mode: ScanMode = ScanMode.QUICK
    custom_instructions: str | None = None


class ScheduleUpdate(BaseModel):
    """Partial update; omitted fields are left unchanged."""

    frequency: ScanFrequency | None = None
    scan_mode: ScanMode | None = None
    custom_instructions: str | None = None
    enabled: bool | None = None


class ScheduleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    repository_id: uuid.UUID
    scan_mode: ScanMode
    frequency: ScanFrequency
    custom_instructions: str | None = None
    enabled: bool
    next_run_at: datetime
    last_run_at: datetime | None = None
    created_at: datetime
