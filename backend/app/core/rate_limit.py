"""Shared slowapi limiter — Redis-backed so limits hold across API workers.

Keyed by client IP. Attached to the app and applied per-endpoint in the auth
router (the abuse-prone surface: login brute-force, signup/email spam).
"""
from __future__ import annotations

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import settings

# Redis in production (limits shared across API workers); in-memory when
# disabled (tests/CI) so no Redis is required just to import the app.
_storage_uri = settings.REDIS_URL if settings.RATE_LIMIT_ENABLED else "memory://"

limiter = Limiter(
    key_func=get_remote_address,
    storage_uri=_storage_uri,
    enabled=settings.RATE_LIMIT_ENABLED,
)
