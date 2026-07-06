"""User persistence helpers (lookup + GitHub upsert + email/password)."""
from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core import security
from app.models.user import User

# A pre-computed bcrypt hash of a throwaway password. Verifying against it when
# no user (or no password) is found keeps login timing ~constant, avoiding an
# oracle that distinguishes "unknown email" from "wrong password".
_DUMMY_HASH = security.get_password_hash("aegis-timing-equalizer")


class EmailAlreadyExistsError(Exception):
    """Raised when registering an email that is already taken."""


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


def create_user_with_password(db: Session, *, email: str, password: str) -> User:
    """Create a new email/password user.

    Raises ``EmailAlreadyExistsError`` if the email is taken (checked up front
    and again on the unique constraint to close the concurrent-signup race).
    """
    normalized = email.strip().lower()
    if get_user_by_email(db, normalized) is not None:
        raise EmailAlreadyExistsError(normalized)

    user = User(
        email=normalized,
        hashed_password=security.get_password_hash(password),
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise EmailAlreadyExistsError(normalized) from exc
    db.refresh(user)
    return user


def set_password(db: Session, user: User, new_password: str) -> User:
    """Replace the user's password hash (used by the reset flow)."""
    user.hashed_password = security.get_password_hash(new_password)
    db.commit()
    db.refresh(user)
    return user


def authenticate_user(db: Session, *, email: str, password: str) -> Optional[User]:
    """Return the user iff the email/password pair is valid, else None."""
    user = get_user_by_email(db, email.strip().lower())
    if user is None or not user.hashed_password:
        # Equalize timing whether or not the account exists / has a password.
        security.verify_password(password, _DUMMY_HASH)
        return None
    if not security.verify_password(password, user.hashed_password):
        return None
    return user


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
