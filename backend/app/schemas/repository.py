"""Repository request/response schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RepositoryRead(BaseModel):
    """A repository connected to the user's dashboard (persisted)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    github_repo_id: str
    name: str
    url: str
    has_greybox: bool = False
    created_at: datetime


class GitHubRepo(BaseModel):
    """A repository available on GitHub but not necessarily connected yet."""

    github_repo_id: str
    name: str
    url: str
    private: bool = False
    description: str | None = None


class RepositorySyncRequest(BaseModel):
    """Payload to connect/sync a GitHub repository to the dashboard."""

    github_repo_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    url: str = Field(..., min_length=1)
