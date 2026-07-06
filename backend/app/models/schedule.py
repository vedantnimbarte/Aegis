"""Schedule model — a recurring scan configuration for a repository."""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDMixin, str_enum
from app.models.enums import ScanFrequency, ScanMode

if TYPE_CHECKING:
    from app.models.repository import Repository


class Schedule(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "schedules"
    __table_args__ = (
        # At most one recurring schedule per repository.
        UniqueConstraint("repository_id", name="uq_schedule_repository"),
    )

    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    scan_mode: Mapped[ScanMode] = mapped_column(
        str_enum(ScanMode, "scan_mode"),
        default=ScanMode.QUICK,
        server_default=ScanMode.QUICK.value,
        nullable=False,
    )
    frequency: Mapped[ScanFrequency] = mapped_column(
        str_enum(ScanFrequency, "scan_frequency"),
        default=ScanFrequency.WEEKLY,
        server_default=ScanFrequency.WEEKLY.value,
        nullable=False,
    )
    custom_instructions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    enabled: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )
    # The scheduler dispatches a scan when now >= next_run_at, then advances it.
    next_run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    last_run_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships -------------------------------------------------------
    repository: Mapped["Repository"] = relationship(back_populates="schedule")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Schedule id={self.id} repo={self.repository_id} freq={self.frequency.value}>"
