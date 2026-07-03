"""AES-256-GCM encryption utilities and a SQLAlchemy TypeDecorator.

Used to encrypt sensitive columns (e.g. `users.github_token`) at rest, as
required by the security spec. The `EncryptedString` type transparently
encrypts on write and decrypts on read, so model code deals with plaintext.

Storage format (base64 of):  [12-byte nonce][ciphertext + 16-byte GCM tag]
"""
from __future__ import annotations

import base64
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import String, TypeDecorator

from app.core.config import settings

_NONCE_BYTES = 12  # 96-bit nonce recommended for GCM


def _load_key() -> bytes:
    """Decode the configured 32-byte key from URL-safe base64."""
    raw = base64.urlsafe_b64decode(settings.ENCRYPTION_KEY)
    if len(raw) != 32:
        raise ValueError(
            "ENCRYPTION_KEY must decode to exactly 32 bytes for AES-256-GCM"
        )
    return raw


def encrypt(plaintext: str) -> str:
    """Encrypt a UTF-8 string, returning a base64-encoded token."""
    aesgcm = AESGCM(_load_key())
    nonce = os.urandom(_NONCE_BYTES)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    return base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")


def decrypt(token: str) -> str:
    """Reverse of `encrypt`. Raises if the token has been tampered with."""
    aesgcm = AESGCM(_load_key())
    blob = base64.urlsafe_b64decode(token)
    nonce, ciphertext = blob[:_NONCE_BYTES], blob[_NONCE_BYTES:]
    return aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")


class EncryptedString(TypeDecorator):
    """A String column that is encrypted at rest with AES-256-GCM."""

    impl = String
    cache_ok = True

    def process_bind_param(self, value: str | None, dialect) -> str | None:
        if value is None:
            return None
        return encrypt(value)

    def process_result_value(self, value: str | None, dialect) -> str | None:
        if value is None:
            return None
        return decrypt(value)
