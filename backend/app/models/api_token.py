"""API token — machine credentials for the public API and CI.

Only a SHA-256 digest of the token is stored. The plaintext is shown once, at
creation, and is unrecoverable afterwards: a leaked database should not hand
an attacker the ability to launch scans against a customer's production
systems.

Tokens act *as the organization*, with a role of their own, so a CI pipeline
can be given exactly the authority to launch scans and read reports without
also being able to invite members or change billing.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDMixin, str_enum
from app.models.enums import OrgRole

if TYPE_CHECKING:
    from app.models.organization import Organization
    from app.models.user import User


class ApiToken(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "api_tokens"

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Human label ("CI — deploy pipeline") so a token can be revoked by name.
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    # SHA-256 hex digest of the plaintext token. Unique so lookup is one index
    # hit rather than a scan-and-compare over every row.
    token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    # First characters of the plaintext, e.g. "aeg_7d21" — enough for a human
    # to match a token in the UI against one in their CI settings.
    token_prefix: Mapped[str] = mapped_column(String(16), nullable=False)

    role: Mapped[OrgRole] = mapped_column(
        str_enum(OrgRole, "org_role"),
        default=OrgRole.MEMBER,
        server_default=OrgRole.MEMBER.value,
        nullable=False,
    )

    last_used_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    organization: Mapped["Organization"] = relationship()
    created_by: Mapped[Optional["User"]] = relationship(
        foreign_keys=[created_by_user_id]
    )

    def is_usable(self, now: datetime) -> bool:
        """Whether this token may still authenticate a request."""
        if self.revoked_at is not None:
            return False
        return self.expires_at is None or self.expires_at > now

    def __repr__(self) -> str:  # pragma: no cover
        return f"<ApiToken {self.token_prefix}… org={self.organization_id}>"
