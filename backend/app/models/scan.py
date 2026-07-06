"""Scan model — one execution of the Strix engine against a repository."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDMixin, str_enum
from app.models.enums import ScanMode, ScanStatus, ScanTrigger

if TYPE_CHECKING:
    from app.models.repository import Repository
    from app.models.vulnerability import Vulnerability


class Scan(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "scans"

    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
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

    # What kicked off this scan (manual / scheduled / pull_request).
    trigger: Mapped[ScanTrigger] = mapped_column(
        str_enum(ScanTrigger, "scan_trigger"),
        default=ScanTrigger.MANUAL,
        server_default=ScanTrigger.MANUAL.value,
        nullable=False,
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
    # URL of the auto-fix pull request, once generated.
    autofix_pr_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)

    started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships -------------------------------------------------------
    repository: Mapped["Repository"] = relationship(back_populates="scans")
    vulnerabilities: Mapped[List["Vulnerability"]] = relationship(
        back_populates="scan",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Scan id={self.id} status={self.status.value}>"
