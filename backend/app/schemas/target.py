"""Target request/response schemas.

One create model rather than five, because a target is one table: the payload
carries a ``kind`` and the fields that kind needs, and the service rejects the
combinations that make no sense (a web target with no URL, a repo with no
clone URL). Five near-identical models would only move that check into
Pydantic and duplicate everything else.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import GitProvider, TargetKind


def _http_url(value: str | None) -> str | None:
    """Normalize an optional http(s) URL, rejecting other schemes.

    A target is something we point exploit traffic at, so ``file://`` or
    ``gopher://`` slipping through is not a cosmetic problem.
    """
    if value is None:
        return None
    v = value.strip()
    if v and not (v.startswith("http://") or v.startswith("https://")):
        raise ValueError("must be an http(s) URL")
    return v or None


class TargetCreate(BaseModel):
    """Connect something to test.

    Repository targets are normally created through the source-host connect
    flow, which fills ``provider``/``external_repo_id`` for you; this model
    also allows a plain clone URL for self-hosted git.
    """

    kind: TargetKind = TargetKind.WEB
    name: str | None = None

    # Repository fields
    provider: GitProvider | None = None
    external_repo_id: str | None = None
    clone_url: str | None = None

    # Endpoint fields
    url: str | None = None
    openapi_url: str | None = None

    # Guardrails
    max_budget_usd: float | None = Field(default=None, ge=0)
    gate_fail_severities: str | None = None
    gate_new_findings_only: bool | None = None
    discovery_enabled: bool | None = None

    @field_validator("url", "openapi_url")
    @classmethod
    def _validate_urls(cls, v: str | None) -> str | None:
        return _http_url(v)


class TargetUpdate(BaseModel):
    """Partial update; omitted fields are left unchanged.

    ``kind`` and ``provider`` are absent on purpose — changing what a target
    *is* would orphan its scan history and every triage verdict keyed to it.
    """

    name: str | None = None
    url: str | None = None
    clone_url: str | None = None
    openapi_url: str | None = None
    max_budget_usd: float | None = Field(default=None, ge=0)
    gate_fail_severities: str | None = None
    gate_new_findings_only: bool | None = None
    discovery_enabled: bool | None = None

    @field_validator("url", "openapi_url")
    @classmethod
    def _validate_urls(cls, v: str | None) -> str | None:
        return _http_url(v)


class TargetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    organization_id: uuid.UUID
    kind: TargetKind
    name: str
    provider: GitProvider | None = None
    external_repo_id: str | None = None
    clone_url: str | None = None
    url: str | None = None
    openapi_url: str | None = None
    has_greybox: bool = False
    has_derived_spec: bool = False
    max_budget_usd: float | None = None
    gate_fail_severities: str | None = None
    gate_new_findings_only: bool = True
    discovery_enabled: bool = False
    discovered_from_id: uuid.UUID | None = None
    created_at: datetime

    @classmethod
    def from_model(cls, target) -> "TargetRead":
        read = cls.model_validate(target)
        read.has_derived_spec = bool(target.derived_spec)
        return read


class SourceRepo(BaseModel):
    """A repository available on a source host but not necessarily connected."""

    provider: GitProvider
    external_repo_id: str
    name: str
    clone_url: str
    private: bool = False
    description: str | None = None


class RepoConnectRequest(BaseModel):
    """Connect a repository from a source host to the organization."""

    provider: GitProvider = GitProvider.GITHUB
    external_repo_id: str = Field(..., min_length=1)
    name: str = Field(..., min_length=1)
    clone_url: str = Field(..., min_length=1)
