"""Token-related request/response schemas."""
from __future__ import annotations

from pydantic import BaseModel


class Token(BaseModel):
    """The JWT pair returned to the client after authentication."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """Decoded JWT claims we care about."""

    sub: str | None = None
    type: str | None = None
    exp: int | None = None
