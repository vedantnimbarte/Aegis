"""Scan and vulnerability request/response schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import ScanMode, ScanStatus, ScanTrigger, Severity


class ScanCreate(BaseModel):
    """Payload to trigger a new scan."""

    repository_id: uuid.UUID
    scan_mode: ScanMode = ScanMode.QUICK
    custom_instructions: str | None = None


class ScanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    repository_id: uuid.UUID
    status: ScanStatus
    scan_mode: ScanMode
    trigger: ScanTrigger
    github_pr_number: int | None = None
    autofix_pr_url: str | None = None
    custom_instructions: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime


class VulnerabilityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    severity: Severity
    title: str
    description: str
    poc_code: str | None = None
    remediation: str | None = None
    owasp_category: str | None = None
    cvss_score: float | None = None
    file_path: str | None = None
    has_fix: bool = False


class ScanReport(BaseModel):
    """Detailed report: scan metadata + findings grouped by severity."""

    scan: ScanRead
    total: int
    counts_by_severity: dict[str, int]
    fixable_count: int = 0
    vulnerabilities: list[VulnerabilityRead]


class AutofixResponse(BaseModel):
    pull_request_url: str
