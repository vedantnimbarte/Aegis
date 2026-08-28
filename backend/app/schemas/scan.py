"""Scan and vulnerability request/response schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import (
    ScanMode,
    ScanStatus,
    ScanTrigger,
    Severity,
    TriageStatus,
)


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
    cost_usd: float | None = None
    llm_requests: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None

    # Finding summary, so a list row can show the outcome without fetching the
    # full report. `None` means "not computed" (single-scan reads don't pay for
    # the aggregate); a completed scan with nothing found returns all zeros.
    counts_by_severity: dict[str, int] | None = None
    findings_total: int | None = None


class DashboardSummary(BaseModel):
    """Portfolio-wide current state, aggregated server-side.

    Counts come from the latest completed scan of each repository, so a
    finding that persists across ten re-scans is counted once — not ten times,
    which is what summing every scan's report would do.
    """

    total_scans: int = 0
    running_scans: int = 0
    connected_repos: int = 0
    scanned_repos: int = 0
    counts_by_severity: dict[str, int] = {}
    open_findings: int = 0
    suppressed_findings: int = 0
    last_scan_at: datetime | None = None


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
    fingerprint: str | None = None
    triage_status: str = "open"
    triage_note: str | None = None
    github_issue_url: str | None = None
    is_new: bool = False


class ScanDiffRead(BaseModel):
    """How a scan compares with the previous completed scan of the same repo."""

    has_baseline: bool = False
    previous_scan_id: uuid.UUID | None = None
    new_count: int = 0
    fixed_count: int = 0
    persisting_count: int = 0


class ScanReport(BaseModel):
    """Detailed report: scan metadata + findings grouped by severity."""

    scan: ScanRead
    total: int
    counts_by_severity: dict[str, int]
    fixable_count: int = 0
    open_count: int = 0
    suppressed_count: int = 0
    diff: ScanDiffRead = ScanDiffRead()
    vulnerabilities: list[VulnerabilityRead]


class TriageUpdate(BaseModel):
    """Set a human verdict on a finding (carried forward to later scans)."""

    status: TriageStatus
    note: str | None = None


class AutofixResponse(BaseModel):
    pull_request_url: str


class FindingIssueResponse(BaseModel):
    """The GitHub issue tracking a finding (existing or newly opened)."""

    issue_url: str
    created: bool = True


class ProgressStepRead(BaseModel):
    """One agent task, shown as a step while a scan runs."""

    title: str
    detail: str | None = None
    status: str = "pending"  # pending | active | done
    agent: str | None = None


class ScanProgressRead(BaseModel):
    """Live progress of an in-flight scan (best-effort; empty before Strix starts)."""

    status: ScanStatus
    phase: str = "starting"
    run_id: str | None = None
    steps: list[ProgressStepRead] = []
    agents: list[dict[str, str]] = []
    llm_requests: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float | None = None
