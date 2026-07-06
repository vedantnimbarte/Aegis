"""GitHub App installation persistence (linking installs to Aegis accounts)."""
from __future__ import annotations

import uuid
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.installation import Installation
from app.models.user import User


def list_installations(db: Session, user: User) -> Sequence[Installation]:
    return db.execute(
        select(Installation)
        .where(Installation.user_id == user.id)
        .order_by(Installation.created_at.desc())
    ).scalars().all()


def get_by_installation_id(db: Session, installation_id: str) -> Optional[Installation]:
    return db.execute(
        select(Installation).where(Installation.installation_id == installation_id)
    ).scalar_one_or_none()


def get_by_account(
    db: Session, user: User, account_login: str
) -> Optional[Installation]:
    """Find the user's installation on a given account/org (case-insensitive)."""
    return db.execute(
        select(Installation).where(
            Installation.user_id == user.id,
            Installation.account_login.ilike(account_login),
        )
    ).scalar_one_or_none()


def get_installation(
    db: Session, record_id: uuid.UUID, user: User
) -> Optional[Installation]:
    return db.execute(
        select(Installation).where(
            Installation.id == record_id, Installation.user_id == user.id
        )
    ).scalar_one_or_none()


def claim_installation(
    db: Session, user: User, installation_id: str, account_login: str
) -> tuple[Optional[Installation], str]:
    """Link an installation to ``user``.

    Returns ``(installation, "")`` on success, ``(existing, "")`` if this user
    already owns it (idempotent re-claim), or ``(None, "taken")`` if another
    account owns it.
    """
    existing = get_by_installation_id(db, installation_id)
    if existing is not None:
        if existing.user_id == user.id:
            return existing, ""
        return None, "taken"

    installation = Installation(
        installation_id=installation_id,
        user_id=user.id,
        account_login=account_login,
    )
    db.add(installation)
    db.commit()
    db.refresh(installation)
    return installation, ""


def delete_installation(db: Session, installation: Installation) -> None:
    db.delete(installation)
    db.commit()
