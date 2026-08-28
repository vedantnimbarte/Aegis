"""Report share — a expiring, unauthenticated link to one scan report.

The buyer this exists for is the founder in a sales cycle: their prospect's
security reviewer wants the pentest report, and creating them a dashboard
account is not going to happen. A share link hands over exactly one report,
read-only, until it expires.

Like ``ApiToken``, only the digest is stored — a share link is a bearer
credential for a document that lists exactly how to attack the customer.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.scan import Scan
    from app.models.user import User


class ReportShare(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "report_shares"

    scan_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scans.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    # Who it was made for ("Acme security review") — shown in the share list.
    label: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Share links always expire. A permanent one is a leak with a long fuse.
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Whether the recipient sees proof-of-concept exploit code. Off by default:
    # a prospect needs to see that you tested and what you fixed, not a working
    # exploit against your production system.
    include_poc: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )

    view_count: Mapped[int] = mapped_column(
        Integer, default=0, server_default="0", nullable=False
    )
    last_viewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    scan: Mapped["Scan"] = relationship()
    created_by: Mapped[Optional["User"]] = relationship(
        foreign_keys=[created_by_user_id]
    )

    def is_valid(self, now: datetime) -> bool:
        return self.revoked_at is None and self.expires_at > now

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ReportShare scan={self.scan_id} expires={self.expires_at}>"
