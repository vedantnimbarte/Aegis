"""Scan model — one execution of the Strix engine against a target."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDMixin, str_enum
from app.models.enums import RetestOutcome, ScanMode, ScanStatus, ScanTrigger

if TYPE_CHECKING:
    from app.models.target import Target
    from app.models.user import User
    from app.models.vulnerability import Vulnerability


class Scan(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "scans"

    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("targets.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # Who launched it. NULL for scheduler- and webhook-initiated scans.
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    status: Mapped[ScanStatus] = mapped_column(
        str_enum(ScanStatus, "scan_status"),
        default=ScanStatus.PENDING,
        server_default=ScanStatus.PENDING.value,
        index=True,
        nullable=False,
    )
    scan_mode: Mapped[ScanMode] = mapped_column(
        str_enum(ScanMode, "scan_mode"),
        default=ScanMode.QUICK,
        server_default=ScanMode.QUICK.value,
        nullable=False,
    )

    # Optional free-text instructions passed to Strix agents.
    custom_instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # What kicked off this scan (manual / scheduled / pull_request / retest).
    trigger: Mapped[ScanTrigger] = mapped_column(
        str_enum(ScanTrigger, "scan_trigger"),
        default=ScanTrigger.MANUAL,
        server_default=ScanTrigger.MANUAL.value,
        nullable=False,
    )

    # --- Retest context (set only for trigger == retest) -----------------
    # The single finding this run exists to re-check. A retest is a scan with
    # a question rather than a survey: does this exploit still work?
    retest_fingerprint: Mapped[Optional[str]] = mapped_column(
        String(64), index=True, nullable=True
    )
    retest_outcome: Mapped[Optional[RetestOutcome]] = mapped_column(
        str_enum(RetestOutcome, "retest_outcome"), nullable=True
    )

    # Pull-request context (set only for GitHub App / pull_request scans).
    github_installation_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    github_pr_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    github_commit_sha: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    github_check_run_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # Celery task id, so the API can trace a scan back to its worker job.
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Populated when status == FAILED.
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # LLM usage for this run, captured from Strix's run.json on completion.
    # Persisted because the run directory is deleted after ingest, and margin
    # per scan is only knowable if we keep it.
    cost_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    llm_requests: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    output_tokens: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    # URL of the auto-fix pull request, once generated.
    autofix_pr_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)

    # The engine build that produced these findings, recorded so a report can
    # answer "what tested this, and when" years later (see services/evidence).
    engine_model: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    # Attack chains computed at ingest: a JSON list of
    # {"title", "severity", "narrative", "fingerprints": [...]}. Stored rather
    # than recomputed so a report never changes shape after it was shared.
    attack_chains: Mapped[Optional[list]] = mapped_column(JSONB, nullable=True)

    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships -------------------------------------------------------
    target: Mapped["Target"] = relationship(back_populates="scans")
    created_by: Mapped[Optional["User"]] = relationship(
        foreign_keys=[created_by_user_id]
    )
    vulnerabilities: Mapped[List["Vulnerability"]] = relationship(
        back_populates="scan",
        cascade="all, delete-orphan",
    )

    @property
    def is_retest(self) -> bool:
        return self.trigger is ScanTrigger.RETEST

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Scan id={self.id} status={self.status.value}>"
