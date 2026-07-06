"""Shared test configuration.

Importing app modules loads `Settings`, which requires a handful of secrets.
Populate dummy values before any app import so unit tests need no real `.env`.
"""
from __future__ import annotations

import base64
import os

os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://aegis:aegis@localhost:5432/aegis")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-that-is-long-enough-000000")
os.environ.setdefault(
    "ENCRYPTION_KEY", base64.urlsafe_b64encode(b"0" * 32).decode("ascii")
)
