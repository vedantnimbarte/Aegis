"""Organization, membership, audit-log and API-token schemas."""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import OrgRole


class OrganizationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    slug: str
    parent_id: uuid.UUID | None = None
    brand_name: str | None = None
    brand_primary_color: str | None = None
    created_at: datetime
    # The caller's own role, so the UI can hide what they cannot do.
    role: OrgRole | None = None
    is_client_workspace: bool = False


class OrganizationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    # Set to create a client workspace beneath an organization you administer.
    parent_id: uuid.UUID | None = None


class OrganizationUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    brand_name: str | None = None
    brand_primary_color: str | None = Field(default=None, max_length=16)


class MemberRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    email: str
    role: OrgRole
    created_at: datetime


class MemberInvite(BaseModel):
    """Add an existing Aegis account to this organization.

    Invitation-by-email for people who have not signed up yet is deliberately
    not here: it needs an invitation token, an acceptance page and an expiry
    policy, and every early team is people who already have accounts.
    """

    email: EmailStr
    role: OrgRole = OrgRole.MEMBER


class MemberRoleUpdate(BaseModel):
    role: OrgRole


class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    action: str
    actor_email: str | None = None
    subject_type: str | None = None
    subject_id: str | None = None
    detail: dict | None = None
    created_at: datetime


class ApiTokenCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    role: OrgRole = OrgRole.MEMBER
    expires_in_days: int | None = Field(default=None, ge=1, le=730)


class ApiTokenRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    token_prefix: str
    role: OrgRole
    last_used_at: datetime | None = None
    expires_at: datetime | None = None
    created_at: datetime


class ApiTokenCreated(ApiTokenRead):
    """Returned once, at creation. ``token`` is never retrievable again."""

    token: str
