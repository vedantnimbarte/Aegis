"""Security primitives: password hashing and JWT creation/decoding.

Tokens are stateless HS256 JWTs. Access tokens are short-lived (15 min by
default); refresh tokens are long-lived and used to mint new access tokens.
Every token carries a ``type`` claim so a refresh token can never be replayed
as an access token (and vice-versa).
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import bcrypt
from jose import jwt

from app.core.config import settings

# Token type claim values.
ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"
PASSWORD_RESET_TOKEN_TYPE = "password_reset"
EMAIL_VERIFY_TOKEN_TYPE = "email_verify"

# bcrypt only considers the first 72 bytes of a password; longer inputs raise
# in bcrypt >= 4.x. We truncate to that limit (standard bcrypt behaviour).
_BCRYPT_MAX_BYTES = 72


def _encode(password: str) -> bytes:
    return password.encode("utf-8")[:_BCRYPT_MAX_BYTES]


# --- Passwords ------------------------------------------------------------
def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(_encode(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(_encode(plain_password), hashed_password.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# --- JWTs -----------------------------------------------------------------
def _create_token(subject: str | Any, token_type: str, expires_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    expire = now + expires_delta
    claims = {
        "sub": str(subject),
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(claims, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(subject: str | Any) -> str:
    return _create_token(
        subject,
        ACCESS_TOKEN_TYPE,
        timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(subject: str | Any) -> str:
    return _create_token(
        subject,
        REFRESH_TOKEN_TYPE,
        timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str) -> dict[str, Any]:
    """Decode and verify a JWT. Raises ``jose.JWTError`` (incl. expiry) on failure."""
    return jwt.decode(
        token,
        settings.JWT_SECRET_KEY,
        algorithms=[settings.JWT_ALGORITHM],
    )


# --- Password reset tokens ------------------------------------------------
def password_fingerprint(hashed_password: Optional[str]) -> str:
    """A short, non-reversible fingerprint of the user's current password.

    Binding a reset token to this value makes the token single-use: once the
    password changes, the fingerprint changes and the outstanding token(s)
    stop verifying. Users with no password yet fingerprint the empty string.
    """
    material = f"{hashed_password or ''}{settings.JWT_SECRET_KEY}".encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:32]


def create_password_reset_token(subject: str | Any, hashed_password: Optional[str]) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(minutes=settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES)
    claims = {
        "sub": str(subject),
        "type": PASSWORD_RESET_TOKEN_TYPE,
        "pwf": password_fingerprint(hashed_password),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(claims, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


# --- Email verification tokens --------------------------------------------
def create_email_verification_token(subject: str | Any) -> str:
    now = datetime.now(timezone.utc)
    expire = now + timedelta(hours=settings.EMAIL_VERIFICATION_TOKEN_EXPIRE_HOURS)
    claims = {
        "sub": str(subject),
        "type": EMAIL_VERIFY_TOKEN_TYPE,
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(claims, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
