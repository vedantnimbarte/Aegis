"""Greybox (authenticated-testing) request/response schemas.

Secrets (``password``, ``extra``) are write-only: reads expose only booleans
indicating whether they are set.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, field_validator


def _require_http_url(value: str | None) -> str | None:
    if value is None:
        return None
    v = value.strip()
    if v and not (v.startswith("http://") or v.startswith("https://")):
        raise ValueError("must be an http(s) URL")
    return v or None


class GreyboxConfigUpsert(BaseModel):
    """Create or update a repo's authenticated-testing config.

    Secret fields left unset are preserved on update; passing an empty string
    clears them.
    """

    target_url: str
    login_url: str | None = None
    username: str | None = None
    password: str | None = None
    extra: str | None = None

    @field_validator("target_url")
    @classmethod
    def _target_is_url(cls, v: str) -> str:
        out = _require_http_url(v)
        if not out:
            raise ValueError("target_url is required")
        return out

    @field_validator("login_url")
    @classmethod
    def _login_is_url(cls, v: str | None) -> str | None:
        return _require_http_url(v)


class GreyboxConfigRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    repository_id: uuid.UUID
    target_url: str
    login_url: str | None = None
    username: str | None = None
    has_password: bool
    has_extra: bool
    created_at: datetime

    @classmethod
    def from_model(cls, config) -> "GreyboxConfigRead":
        return cls(
            id=config.id,
            repository_id=config.repository_id,
            target_url=config.target_url,
            login_url=config.login_url,
            username=config.username,
            has_password=bool(config.password),
            has_extra=bool(config.extra),
            created_at=config.created_at,
        )
