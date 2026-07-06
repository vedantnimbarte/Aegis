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
