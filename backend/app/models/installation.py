"""Installation model — a GitHub App installation linked to an organization.

After a user installs the Aegis GitHub App on their repos/org, GitHub redirects
back with an ``installation_id`` that the signed-in user claims here. Incoming
webhooks are then mapped ``installation_id -> organization`` for multi-tenant
routing: a PR scan belongs to the team, not to whoever happened to click
install.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User

from app.db.base_class import Base, TimestampMixin, UUIDMixin


class Installation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "installations"

    # GitHub's numeric installation id (stored as a string for consistency).
    installation_id: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # Who claimed it — retained for the audit trail.
    claimed_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    # The org/user account the app was installed on (e.g. "acme").
    account_login: Mapped[str] = mapped_column(String(255), nullable=False)

    organization: Mapped["Organization"] = relationship()
    claimed_by: Mapped[Optional["User"]] = relationship(
        foreign_keys=[claimed_by_user_id]
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Installation gh_id={self.installation_id} account={self.account_login!r}>"
