"""User persistence helpers (lookup + GitHub upsert)."""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user import User


def get_user_by_id(db: Session, user_id: str | uuid.UUID) -> Optional[User]:
    """Fetch a user by primary key. Returns None on a malformed UUID."""
    try:
        uid = user_id if isinstance(user_id, uuid.UUID) else uuid.UUID(str(user_id))
    except (ValueError, TypeError):
        return None
    return db.get(User, uid)


def get_user_by_email(db: Session, email: str) -> Optional[User]:
    return db.execute(
        select(User).where(User.email == email)
    ).scalar_one_or_none()


def upsert_user_from_github(
    db: Session,
    *,
    email: str,
    github_username: Optional[str],
    github_token: str,
) -> User:
    """Create or update a user from a GitHub OAuth login.

    Users are keyed by email (the unique column in the schema). The GitHub
    token is stored via the `EncryptedString` column type, i.e. encrypted at
    rest with AES-256-GCM.
    """
    user = get_user_by_email(db, email)
    if user is None:
        user = User(
            email=email,
            github_username=github_username,
            github_token=github_token,
        )
        db.add(user)
    else:
        user.github_username = github_username
        user.github_token = github_token

    db.commit()
    db.refresh(user)
    return user
