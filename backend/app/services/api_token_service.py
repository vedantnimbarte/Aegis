"""Issue, verify and revoke API tokens.

The plaintext token is returned exactly once, from ``issue``. Everything
afterwards works off a SHA-256 digest, so the database never holds a
credential that can launch attacks against a customer's production estate.

SHA-256 rather than bcrypt here on purpose: a 256-bit random token has no
guessable structure, so the slow hash that protects a human-chosen password
buys nothing, while costing a KDF round on every API request.
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.api_token import ApiToken
from app.models.enums import OrgRole
from app.models.organization import Organization
from app.models.user import User

# Recognisable in a log or a CI settings page, and greppable in a leak scan.
TOKEN_PREFIX = "aeg_"
_TOKEN_BYTES = 32
_PREFIX_CHARS = 12


def hash_token(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def generate_token() -> str:
    return f"{TOKEN_PREFIX}{secrets.token_urlsafe(_TOKEN_BYTES)}"


def issue(
    db: Session,
    *,
    org: Organization,
    creator: Optional[User],
    name: str,
    role: OrgRole = OrgRole.MEMBER,
    expires_in_days: Optional[int] = None,
) -> tuple[ApiToken, str]:
    """Create a token. Returns ``(row, plaintext)`` — the plaintext is final."""
    plaintext = generate_token()
    token = ApiToken(
        organization_id=org.id,
        created_by_user_id=creator.id if creator is not None else None,
        name=name.strip()[:128] or "API token",
        token_hash=hash_token(plaintext),
        token_prefix=plaintext[:_PREFIX_CHARS],
        role=role,
        expires_at=(
            datetime.now(timezone.utc) + timedelta(days=expires_in_days)
            if expires_in_days
            else None
        ),
    )
    db.add(token)
    db.commit()
    db.refresh(token)
    return token, plaintext


def resolve(db: Session, plaintext: str) -> Optional[ApiToken]:
    """The usable token matching ``plaintext``, or None.

    Records ``last_used_at`` so a stale token can be spotted and revoked. The
    stamp is best-effort — failing to update it must not fail the request.
    """
    if not plaintext.startswith(TOKEN_PREFIX):
        return None
    token = db.execute(
        select(ApiToken).where(ApiToken.token_hash == hash_token(plaintext))
    ).scalar_one_or_none()
    if token is None or not token.is_usable(datetime.now(timezone.utc)):
        return None

    try:
        token.last_used_at = datetime.now(timezone.utc)
        db.commit()
    except Exception:  # noqa: BLE001 - usage tracking is not worth a 500
        db.rollback()
    return token


def list_tokens(db: Session, org: Organization) -> Sequence[ApiToken]:
    return (
        db.execute(
            select(ApiToken)
            .where(ApiToken.organization_id == org.id, ApiToken.revoked_at.is_(None))
            .order_by(ApiToken.created_at.desc())
        )
        .scalars()
        .all()
    )


def get_token(
    db: Session, org: Organization, token_id: uuid.UUID
) -> Optional[ApiToken]:
    return db.execute(
        select(ApiToken).where(
            ApiToken.id == token_id, ApiToken.organization_id == org.id
        )
    ).scalar_one_or_none()


def revoke(db: Session, token: ApiToken) -> ApiToken:
    """Revoke rather than delete, so the audit log still resolves the id."""
    if token.revoked_at is None:
        token.revoked_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(token)
    return token
