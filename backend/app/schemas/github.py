"""GitHub App request/response schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class InstallationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    installation_id: str
    account_login: str
    created_at: datetime


class InstallationClaimRequest(BaseModel):
    """Claim a GitHub App installation after the post-install redirect."""

    installation_id: str = Field(..., min_length=1)


class GitHubAppInfo(BaseModel):
    """Everything the dashboard needs to render the GitHub App integration."""

    configured: bool
    install_url: str
    installations: list[InstallationRead]
