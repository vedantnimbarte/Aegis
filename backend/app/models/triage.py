"""Finding triage — a human verdict that outlives the scan that produced it.

Triage is keyed by ``(repository_id, fingerprint)`` rather than by
``vulnerability_id`` on purpose: every re-scan produces brand-new
``Vulnerability`` rows, so a verdict stored on the row would be forgotten the
next time the same issue is reported. Keying on the fingerprint means marking
something a false positive once keeps it suppressed on every later scan of
that repository.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDMixin, str_enum
from app.models.enums import TriageStatus

if TYPE_CHECKING:
    from app.models.repository import Repository


class FindingTriage(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "finding_triage"
    __table_args__ = (
        UniqueConstraint("repository_id", "fingerprint", name="uq_triage_repo_finding"),
    )

    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
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

    # GitHub issue opened for this finding, if any. Stored here (rather than
    # on the vulnerability row) so re-scans reuse the issue instead of
    # opening a duplicate for the same fingerprint.
    github_issue_url: Mapped[Optional[str]] = mapped_column(
        String(512), nullable=True
    )

    repository: Mapped["Repository"] = relationship()
