"""Organization membership, roles, and the agency/client hierarchy.

Two rules run through everything here:

* **Authority is a role in an organization**, never "I created this row".
  Every lookup takes the acting user and resolves their membership; a user
  with no membership sees nothing, including their own former rows.

* **A parent organization's members act in its children.** That is the whole
  of the agency/MSSP model: an agency organization holds client workspaces,
  and an agency admin inherits their role in each. Inheritance is one level
  deep on purpose — a tree of arbitrary depth is a permissions puzzle nobody
  asked for.
"""
from __future__ import annotations

import re
import secrets
import uuid
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import ROLE_RANK, OrgRole
from app.models.organization import Organization, OrgMembership
from app.models.user import User

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")


def slugify(value: str) -> str:
    """A URL-safe handle. Never empty — a blank slug is not addressable."""
    slug = _SLUG_STRIP.sub("-", value.strip().lower()).strip("-")
    return slug or "org"


def _unique_slug(db: Session, base: str) -> str:
    """``base``, suffixed until no organization holds it.

    Collisions are rare, so a bounded retry beats a uniqueness dance; after a
    few attempts we stop guessing and use random entropy.
    """
    slug = slugify(base)
    for attempt in range(5):
        taken = db.execute(
            select(Organization.id).where(Organization.slug == slug)
        ).scalar_one_or_none()
        if taken is None:
            return slug
        slug = f"{slugify(base)}-{secrets.token_hex(2 + attempt)}"
    return f"{slugify(base)}-{uuid.uuid4().hex[:12]}"


# --- Creation -------------------------------------------------------------
def create_organization(
    db: Session,
    *,
    name: str,
    owner: User,
    parent: Optional[Organization] = None,
) -> Organization:
    """Create an organization owned by ``owner``, who becomes its OWNER member."""
    org = Organization(
        name=name.strip() or owner.email.split("@")[0],
        slug=_unique_slug(db, name or owner.email.split("@")[0]),
        owner_user_id=owner.id,
        parent_id=parent.id if parent is not None else None,
    )
    db.add(org)
    db.flush()
    db.add(
        OrgMembership(organization_id=org.id, user_id=owner.id, role=OrgRole.OWNER)
    )
    db.commit()
    db.refresh(org)
    return org


def ensure_personal_organization(db: Session, user: User) -> Organization:
    """The user's own organization, created on first use.

    New sign-ups get one lazily rather than in the auth endpoint, so every
    path that needs an organization — including a user who predates
    organizations entirely — finds one.
    """
    existing = db.execute(
        select(Organization)
        .join(OrgMembership, OrgMembership.organization_id == Organization.id)
        .where(OrgMembership.user_id == user.id)
        .order_by(Organization.created_at.asc())
        .limit(1)
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    return create_organization(db, name=user.email.split("@")[0], owner=user)


# --- Lookup ---------------------------------------------------------------
def list_organizations(db: Session, user: User) -> Sequence[Organization]:
    """Every organization the user is a member of, oldest first."""
    return (
        db.execute(
            select(Organization)
            .join(OrgMembership, OrgMembership.organization_id == Organization.id)
            .where(OrgMembership.user_id == user.id)
            .order_by(Organization.created_at.asc())
        )
        .scalars()
        .all()
    )


def get_organization(
    db: Session, organization_id: uuid.UUID, user: User
) -> Optional[Organization]:
    """An organization the user can act in, directly or via its parent."""
    org = db.get(Organization, organization_id)
    if org is None:
        return None
    return org if role_in(db, org, user) is not None else None


def role_in(db: Session, org: Organization, user: User) -> Optional[OrgRole]:
    """The user's effective role in ``org``, or None if they are not a member.

    A member of the parent organization inherits their parent role here, which
    is what lets an agency operate its clients' workspaces.
    """
    direct = db.execute(
        select(OrgMembership.role).where(
            OrgMembership.organization_id == org.id,
            OrgMembership.user_id == user.id,
        )
    ).scalar_one_or_none()
    if direct is not None:
        return direct
    if org.parent_id is None:
        return None
    return db.execute(
        select(OrgMembership.role).where(
            OrgMembership.organization_id == org.parent_id,
            OrgMembership.user_id == user.id,
        )
    ).scalar_one_or_none()


def has_role(
    db: Session, org: Organization, user: User, minimum: OrgRole
) -> bool:
    """Whether the user's role in ``org`` is at least ``minimum``."""
    role = role_in(db, org, user)
    if role is None:
        return False
    return ROLE_RANK[role] >= ROLE_RANK[minimum]


def accessible_organization_ids(db: Session, user: User) -> list[uuid.UUID]:
    """Every organization id the user can read, including client workspaces.

    Used by the cross-organization views (portfolio summary, cost reporting)
    so an agency sees all its clients in one place.
    """
    direct = list(
        db.execute(
            select(OrgMembership.organization_id).where(
                OrgMembership.user_id == user.id
            )
        )
        .scalars()
        .all()
    )
    if not direct:
        return []
    children = list(
        db.execute(
            select(Organization.id).where(Organization.parent_id.in_(direct))
        )
        .scalars()
        .all()
    )
    # dict.fromkeys preserves order while removing the overlap a user who is
    # a member of both an agency and one of its clients would otherwise get.
    return list(dict.fromkeys(direct + children))


# --- Membership management ------------------------------------------------
def list_members(db: Session, org: Organization) -> Sequence[OrgMembership]:
    return (
        db.execute(
            select(OrgMembership)
            .where(OrgMembership.organization_id == org.id)
            .order_by(OrgMembership.created_at.asc())
        )
        .scalars()
        .all()
    )


def add_member(
    db: Session, org: Organization, user: User, role: OrgRole
) -> OrgMembership:
    """Add (or re-role) a user in an organization."""
    membership = db.execute(
        select(OrgMembership).where(
            OrgMembership.organization_id == org.id,
            OrgMembership.user_id == user.id,
        )
    ).scalar_one_or_none()
    if membership is None:
        membership = OrgMembership(
            organization_id=org.id, user_id=user.id, role=role
        )
        db.add(membership)
    else:
        membership.role = role
    db.commit()
    db.refresh(membership)
    return membership


def remove_member(db: Session, membership: OrgMembership) -> bool:
    """Remove a seat. Refuses to strip the organization of its owner.

    An organization with no owner has no subscription behind it and nobody who
    can restore one, so the last owner cannot be removed — the account has to
    be transferred first.
    """
    if membership.role is OrgRole.OWNER:
        remaining = db.execute(
            select(OrgMembership.id).where(
                OrgMembership.organization_id == membership.organization_id,
                OrgMembership.role == OrgRole.OWNER,
                OrgMembership.id != membership.id,
            )
        ).first()
        if remaining is None:
            return False
    db.delete(membership)
    db.commit()
    return True


def get_membership(
    db: Session, org: Organization, membership_id: uuid.UUID
) -> Optional[OrgMembership]:
    return db.execute(
        select(OrgMembership).where(
            OrgMembership.id == membership_id,
            OrgMembership.organization_id == org.id,
        )
    ).scalar_one_or_none()


# --- Entitlement ----------------------------------------------------------
def billing_user(db: Session, org: Organization) -> User:
    """The user whose subscription entitles this organization.

    A client workspace bills to its agency: the agency signed the contract,
    and asking each client to hold their own card defeats the point.
    """
    if org.parent_id is not None:
        parent = db.get(Organization, org.parent_id)
        if parent is not None:
            return parent.owner
    return org.owner
