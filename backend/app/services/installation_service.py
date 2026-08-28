"""GitHub App installation persistence (linking installs to organizations).

An installation belongs to the organization, not to whoever happened to
click install: a pull-request scan is the team's, and it must keep working
after that person leaves.
"""
from __future__ import annotations

import uuid
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.installation import Installation
from app.models.organization import Organization
from app.models.user import User


def list_installations(db: Session, org: Organization) -> Sequence[Installation]:
    return db.execute(
        select(Installation)
        .where(Installation.organization_id == org.id)
        .order_by(Installation.created_at.desc())
    ).scalars().all()


def get_by_installation_id(db: Session, installation_id: str) -> Optional[Installation]:
    return db.execute(
        select(Installation).where(Installation.installation_id == installation_id)
    ).scalar_one_or_none()


def get_by_account(
    db: Session, organization_id: uuid.UUID, account_login: str
) -> Optional[Installation]:
    """The organization's installation on a given account/org (case-insensitive)."""
    return db.execute(
        select(Installation).where(
            Installation.organization_id == organization_id,
            Installation.account_login.ilike(account_login),
        )
    ).scalar_one_or_none()


def get_installation(
    db: Session, record_id: uuid.UUID, org: Organization
) -> Optional[Installation]:
    return db.execute(
        select(Installation).where(
            Installation.id == record_id, Installation.organization_id == org.id
        )
    ).scalar_one_or_none()


def claim_installation(
    db: Session,
    org: Organization,
    installation_id: str,
    account_login: str,
    claimed_by: Optional[User] = None,
) -> tuple[Optional[Installation], str]:
    """Link an installation to ``org``.

    Returns ``(installation, "")`` on success, ``(existing, "")`` if this
    organization already holds it (idempotent re-claim), or ``(None, "taken")``
    if another organization does.
    """
    existing = get_by_installation_id(db, installation_id)
    if existing is not None:
        if existing.organization_id == org.id:
            return existing, ""
        return None, "taken"

    installation = Installation(
        installation_id=installation_id,
        organization_id=org.id,
        claimed_by_user_id=claimed_by.id if claimed_by is not None else None,
        account_login=account_login,
    )
    db.add(installation)
    db.commit()
    db.refresh(installation)
    return installation, ""


def delete_installation(db: Session, installation: Installation) -> None:
    db.delete(installation)
    db.commit()
