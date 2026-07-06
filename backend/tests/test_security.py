"""Tests for password hashing and JWT primitives (core/security.py)."""
from __future__ import annotations

import pytest
from jose import JWTError

from app.core import security


def test_password_hash_roundtrip() -> None:
    h = security.get_password_hash("correct horse battery staple")
    assert h != "correct horse battery staple"  # never store plaintext
    assert security.verify_password("correct horse battery staple", h) is True
    assert security.verify_password("wrong password", h) is False


def test_password_hashes_are_salted() -> None:
    a = security.get_password_hash("same-password")
    b = security.get_password_hash("same-password")
    assert a != b  # distinct salts
    assert security.verify_password("same-password", a)
    assert security.verify_password("same-password", b)


def test_verify_password_tolerates_garbage_hash() -> None:
    assert security.verify_password("whatever", "not-a-bcrypt-hash") is False


def test_long_password_is_truncated_not_rejected() -> None:
    # bcrypt only considers the first 72 bytes; a longer password must not raise.
    pw = "a" * 200
    h = security.get_password_hash(pw)
    assert security.verify_password(pw, h) is True
    # First 72 bytes identical -> still verifies (documented bcrypt behavior).
    assert security.verify_password("a" * 72, h) is True


def test_access_token_roundtrip() -> None:
    token = security.create_access_token("user-123")
    claims = security.decode_token(token)
    assert claims["sub"] == "user-123"
    assert claims["type"] == security.ACCESS_TOKEN_TYPE


def test_refresh_token_has_distinct_type() -> None:
    claims = security.decode_token(security.create_refresh_token("user-123"))
    assert claims["type"] == security.REFRESH_TOKEN_TYPE


def test_tampered_token_is_rejected() -> None:
    token = security.create_access_token("user-123")
    with pytest.raises(JWTError):
        security.decode_token(token + "tampered")


# --- Password reset tokens ------------------------------------------------
def test_password_reset_token_carries_type_and_fingerprint() -> None:
    hashed = security.get_password_hash("old-password")
    token = security.create_password_reset_token("user-123", hashed)
    claims = security.decode_token(token)
    assert claims["sub"] == "user-123"
    assert claims["type"] == security.PASSWORD_RESET_TOKEN_TYPE
    assert claims["pwf"] == security.password_fingerprint(hashed)


def test_reset_token_is_not_an_access_token() -> None:
    token = security.create_password_reset_token("user-123", "hash")
    assert security.decode_token(token)["type"] != security.ACCESS_TOKEN_TYPE


def test_fingerprint_changes_when_password_changes() -> None:
    """This binding is what makes a reset token single-use."""
    old = security.get_password_hash("old-password")
    new = security.get_password_hash("new-password")
    token = security.create_password_reset_token("user-123", old)
    issued_fp = security.decode_token(token)["pwf"]
    # After the password changes, the fingerprint no longer matches -> the
    # token can't be replayed.
    assert issued_fp == security.password_fingerprint(old)
    assert issued_fp != security.password_fingerprint(new)


def test_fingerprint_handles_user_without_password() -> None:
    # GitHub-only users have no password hash; fingerprint must still work.
    assert security.password_fingerprint(None) == security.password_fingerprint("")
    token = security.create_password_reset_token("user-123", None)
    assert security.decode_token(token)["pwf"] == security.password_fingerprint(None)


# --- Email verification tokens --------------------------------------------
def test_email_verification_token_carries_type() -> None:
    token = security.create_email_verification_token("user-123")
    claims = security.decode_token(token)
    assert claims["sub"] == "user-123"
    assert claims["type"] == security.EMAIL_VERIFY_TOKEN_TYPE


def test_verification_token_is_not_a_reset_or_access_token() -> None:
    claims = security.decode_token(security.create_email_verification_token("u"))
    assert claims["type"] != security.ACCESS_TOKEN_TYPE
    assert claims["type"] != security.PASSWORD_RESET_TOKEN_TYPE
