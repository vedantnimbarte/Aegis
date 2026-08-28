"""Organization — the tenancy boundary everything else hangs off.

Targets, scans, findings, integrations and audit history belong to an
organization, not to a person. A user reaches them through an
``OrgMembership`` carrying a role.

Billing deliberately stays on the owner ``User``: Stripe knows about
customers, and giving an organization a second, competing notion of "who
pays" is how double-billing bugs happen. ``owner`` is therefore both the
top-role member and the account the subscription is read from.

``parent_id`` supports the agency/MSSP case: a parent organization holds
client organizations beneath it, and a member of the parent can act in any
child. One level is all that is modelled — a tree of arbitrary depth is a
permissions problem nobody asked us to solve.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDMixin, str_enum
from app.models.enums import OrgRole

if TYPE_CHECKING:
    from app.models.target import Target
    from app.models.user import User


class Organization(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "organizations"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # URL-safe handle, unique platform-wide.
    slug: Mapped[str] = mapped_column(String(128), unique=True, index=True, nullable=False)

    # The member whose Stripe subscription entitles this organization.
    owner_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    # Agency/MSSP: a client workspace nested under the agency's organization.
    parent_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
        nullable=True,
    )

    # --- White-label branding (used on exported reports) -----------------
    brand_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    brand_primary_color: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)

    # Relationships -------------------------------------------------------
    owner: Mapped["User"] = relationship(foreign_keys=[owner_user_id])
    memberships: Mapped[List["OrgMembership"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    targets: Mapped[List["Target"]] = relationship(
        back_populates="organization", cascade="all, delete-orphan"
    )
    children: Mapped[List["Organization"]] = relationship(
        back_populates="parent", cascade="all, delete-orphan"
    )
    parent: Mapped[Optional["Organization"]] = relationship(
        back_populates="children", remote_side="Organization.id"
    )

    @property
    def is_client_workspace(self) -> bool:
        return self.parent_id is not None

    @property
    def display_brand(self) -> str:
        """The name to print on a report — the white-label name if set."""
        return self.brand_name or self.name

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Organization id={self.id} slug={self.slug!r}>"


class OrgMembership(UUIDMixin, TimestampMixin, Base):
    """A user's seat in an organization, carrying their role."""

    __tablename__ = "org_memberships"
    __table_args__ = (
        UniqueConstraint("organization_id", "user_id", name="uq_membership_org_user"),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    role: Mapped[OrgRole] = mapped_column(
        str_enum(OrgRole, "org_role"),
        default=OrgRole.MEMBER,
        server_default=OrgRole.MEMBER.value,
        nullable=False,
    )

    organization: Mapped["Organization"] = relationship(back_populates="memberships")
    user: Mapped["User"] = relationship(back_populates="memberships")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<OrgMembership org={self.organization_id} user={self.user_id} role={self.role.value}>"
