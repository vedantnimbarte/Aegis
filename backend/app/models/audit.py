"""Audit event — an append-only record of who did what in an organization.

Deliberately dumb: a row is written and never updated or deleted by
application code. ``action`` is a stable dotted string (``scan.created``,
``member.role_changed``) so a log can be filtered without parsing prose, and
``detail`` carries whatever context that action needs.

The actor is nullable because the system acts too — a scheduled scan or a
webhook-triggered one has no human behind it, and pretending otherwise would
make the log lie.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User


class AuditEvent(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        # The only query that matters: this org's history, newest first.
        Index("ix_audit_org_created", "organization_id", "created_at"),
    )

    # NULL for account-level events that belong to no organization: signing in
    # is not something you do *to* an org, and a failed sign-in may not even
    # resolve to a user. Org history queries filter on this column, so those
    # events simply never appear in an org's log.
    organization_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )
    # NULL when the platform itself acted (scheduler, webhook, retest worker).
    actor_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Denormalized so the log still reads correctly after a user is deleted.
    actor_email: Mapped[Optional[str]] = mapped_column(String(320), nullable=True)

    action: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    # What the action was performed on, e.g. ("target", <uuid>).
    subject_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    subject_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)

    detail: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    organization: Mapped["Organization"] = relationship()
    actor: Mapped[Optional["User"]] = relationship()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AuditEvent {self.action} org={self.organization_id}>"
