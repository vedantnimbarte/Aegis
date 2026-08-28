"""Scan and vulnerability request/response schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import (
    IssueTracker,
    RetestOutcome,
    ScanMode,
    ScanStatus,
    ScanTrigger,
    Severity,
    TargetKind,
    TriageStatus,
)


class ScanCreate(BaseModel):
    """Payload to trigger a new scan."""

    target_id: uuid.UUID
    scan_mode: ScanMode = ScanMode.QUICK
    custom_instructions: str | None = None


class ScanRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    target_id: uuid.UUID
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
    engine_model: str | None = None
    retest_fingerprint: str | None = None
    retest_outcome: RetestOutcome | None = None

    # Denormalized target context so a scan row renders without a second call.
    target_name: str | None = None
    target_kind: TargetKind | None = None

    # Finding summary, so a list row can show the outcome without fetching the
    # full report. `None` means "not computed" (single-scan reads don't pay for
    # the aggregate); a completed scan with nothing found returns all zeros.
    counts_by_severity: dict[str, int] | None = None
    findings_total: int | None = None


class DashboardSummary(BaseModel):
    """Portfolio-wide current state, aggregated server-side.

    Counts come from the latest completed scan of each target, so a finding
    that persists across ten re-scans is counted once — not ten times, which
    is what summing every scan's report would do.
    """

    total_scans: int = 0
    running_scans: int = 0
    connected_targets: int = 0
    scanned_targets: int = 0
    counts_by_severity: dict[str, int] = {}
    open_findings: int = 0
    suppressed_findings: int = 0
    verified_fixed: int = 0
    last_scan_at: datetime | None = None


class EvidenceRead(BaseModel):
    """What was observed, so a human can confirm a finding without re-running it.

    Every field is optional: the engine does not always capture a transcript,
    and an evidence bundle with gaps is far more useful than none at all.
    """

    request: str | None = None
    response: str | None = None
    poc_output: str | None = None
    target_url: str | None = None
    commit_sha: str | None = None
    engine: str | None = None
    model: str | None = None
    observed_at: str | None = None
    notes: str | None = None


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
    issue_tracker: IssueTracker | None = None
    issue_key: str | None = None
    is_new: bool = False
    evidence: EvidenceRead | None = None
    # Retest verdict carried over from triage, so the report can say "we
    # re-ran this exploit and it no longer works" rather than just "fixed".
    retest_outcome: RetestOutcome | None = None
    retested_at: datetime | None = None


class ScanDiffRead(BaseModel):
    """How a scan compares with the previous completed scan of the same target."""

    has_baseline: bool = False
    previous_scan_id: uuid.UUID | None = None
    new_count: int = 0
    fixed_count: int = 0
    persisting_count: int = 0


class AttackChainRead(BaseModel):
    """Several findings that compose into one, worse outcome."""

    title: str
    severity: Severity
    narrative: str
    fingerprints: list[str] = []
    steps: list[str] = []


class ScanReport(BaseModel):
    """Detailed report: scan metadata + findings grouped by severity."""

    scan: ScanRead
    total: int
    counts_by_severity: dict[str, int]
    fixable_count: int = 0
    open_count: int = 0
    suppressed_count: int = 0
    verified_fixed_count: int = 0
    diff: ScanDiffRead = ScanDiffRead()
    attack_chains: list[AttackChainRead] = []
    vulnerabilities: list[VulnerabilityRead]


class TriageUpdate(BaseModel):
    """Set a human verdict on a finding (carried forward to later scans)."""

    status: TriageStatus
    note: str | None = None


class AutofixResponse(BaseModel):
    pull_request_url: str


class FindingIssueRequest(BaseModel):
    """Where to file this finding. Defaults to whatever the org has set up."""

    tracker: IssueTracker | None = None


class FindingIssueResponse(BaseModel):
    """The issue tracking a finding (existing or newly opened)."""

    issue_url: str
    tracker: IssueTracker
    issue_key: str | None = None
    created: bool = True


class RetestResponse(BaseModel):
    """The retest that was dispatched for one finding."""

    scan_id: uuid.UUID
    fingerprint: str
    status: ScanStatus


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


class ShareCreate(BaseModel):
    """Mint an expiring public link to one report."""

    label: str | None = Field(default=None, max_length=255)
    expires_in_days: int | None = Field(default=None, ge=1, le=365)
    # Off by default: a prospect needs to see that you tested and fixed, not a
    # working exploit against your production system.
    include_poc: bool = False


class ShareRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    scan_id: uuid.UUID
    label: str | None = None
    expires_at: datetime
    include_poc: bool
    view_count: int
    last_viewed_at: datetime | None = None
    created_at: datetime


class ShareCreated(ShareRead):
    """Returned once, at creation. ``url`` embeds the only copy of the token."""

    url: str


class TargetCostRead(BaseModel):
    """What one target cost to test, and what that bought."""

    target_id: uuid.UUID
    target_name: str
    scans: int
    cost_usd: float = 0.0
    findings: int = 0
    validated_findings: int = 0
    cost_per_validated_finding: float | None = None


class CostSummary(BaseModel):
    """Spend the way a buyer of a metered product actually asks about it.

    Nobody else in this category shows the customer their LLM bill. Aegis
    already records ``cost_usd`` per scan, so withholding it would be a choice.
    """

    period_start: datetime
    total_cost_usd: float = 0.0
    total_scans: int = 0
    total_findings: int = 0
    validated_findings: int = 0
    cost_per_scan: float | None = None
    cost_per_validated_finding: float | None = None
    by_target: list[TargetCostRead] = []
    # What the next scan of each depth is expected to cost, from this
    # organization's own history rather than a generic price list.
    forecast_by_mode: dict[str, float] = {}
