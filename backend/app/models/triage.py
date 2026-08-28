"""Finding triage — a human verdict that outlives the scan that produced it.

Triage is keyed by ``(target_id, fingerprint)`` rather than by
``vulnerability_id`` on purpose: every re-scan produces brand-new
``Vulnerability`` rows, so a verdict stored on the row would be forgotten the
next time the same issue is reported. Keying on the fingerprint means marking
something a false positive once keeps it suppressed on every later scan of
that target.

The retest columns live here for the same reason. "This exploit no longer
works" is a fact about the finding, not about the run that happened to prove
it, so it has to survive the next scan too.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDMixin, str_enum
from app.models.enums import IssueTracker, RetestOutcome, TriageStatus

if TYPE_CHECKING:
    from app.models.target import Target


class FindingTriage(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "finding_triage"
    __table_args__ = (
        UniqueConstraint("target_id", "fingerprint", name="uq_triage_target_finding"),
    )

    target_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("targets.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # Matches Vulnerability.fingerprint.
    fingerprint: Mapped[str] = mapped_column(String(64), index=True, nullable=False)

    status: Mapped[TriageStatus] = mapped_column(
        str_enum(TriageStatus, "triage_status"),
        default=TriageStatus.OPEN,
        server_default=TriageStatus.OPEN.value,
        nullable=False,
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Issue opened for this finding, if any. Stored here (rather than on the
    # vulnerability row) so re-scans reuse the issue instead of opening a
    # duplicate for the same fingerprint.
    github_issue_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    # Which tracker the issue above lives in (GitHub, Jira, Linear).
    issue_tracker: Mapped[Optional[IssueTracker]] = mapped_column(
        str_enum(IssueTracker, "issue_tracker"), nullable=True
    )
    # The tracker's own key, e.g. "SEC-214" — what a human quotes in standup.
    issue_key: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    # --- Retest verification ---------------------------------------------
    # Outcome of the last attempt to re-run this finding's proof of concept.
    retest_outcome: Mapped[Optional[RetestOutcome]] = mapped_column(
        str_enum(RetestOutcome, "retest_outcome"), nullable=True
    )
    retested_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_retest_scan_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("scans.id", ondelete="SET NULL"), nullable=True
    )
    # What the retest actually observed, so "fixed" is a claim with a receipt.
    retest_evidence: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    target: Mapped["Target"] = relationship()

    @property
    def is_verified_fixed(self) -> bool:
        """Fixed *and* proven so by re-running the exploit."""
        return self.retest_outcome is RetestOutcome.FIXED
