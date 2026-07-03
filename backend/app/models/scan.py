"""Scan model — one execution of the Strix engine against a repository."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDMixin, str_enum
from app.models.enums import ScanMode, ScanStatus

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

    # Celery task id, so the API can trace a scan back to its worker job.
    celery_task_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Populated when status == FAILED.
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

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
