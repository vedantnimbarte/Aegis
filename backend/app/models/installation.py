"""Installation model — a GitHub App installation linked to an Aegis account.

After a user installs the Aegis GitHub App on their repos/org, GitHub redirects
back with an ``installation_id`` that the signed-in user claims here. Incoming
webhooks are then mapped ``installation_id -> user`` for multi-tenant routing.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.user import User


class Installation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "installations"

    # GitHub's numeric installation id (stored as a string for consistency).
    installation_id: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # The org/user account the app was installed on (e.g. "acme").
    account_login: Mapped[str] = mapped_column(String(255), nullable=False)

    user: Mapped["User"] = relationship()

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Installation gh_id={self.installation_id} account={self.account_login!r}>"
