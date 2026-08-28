"""User response schemas.

Note: tokens, API keys and `hashed_password` are deliberately never exposed —
reads return only booleans saying whether each is configured.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import SubscriptionStatus, SubscriptionTier


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    email_verified: bool
    display_name: str | None = None
    github_username: str | None = None
    has_password: bool = False
    subscription_tier: SubscriptionTier
    subscription_status: SubscriptionStatus
    has_active_subscription: bool
    subscription_current_period_end: datetime | None = None
    stripe_customer_id: str | None = None
    is_active: bool
    created_at: datetime
    has_accepted_scan_terms: bool = False
    # Integrations (secrets themselves are never returned).
    llm_model: str | None = None
    has_llm_key: bool = False
    has_slack: bool = False
    has_jira: bool = False
    has_linear: bool = False
    jira_url: str | None = None
    jira_project_key: str | None = None
    linear_team_id: str | None = None


class UserIntegrationsUpdate(BaseModel):
    """Partial update of a user's integration settings.

    Only fields that are present are changed (PATCH semantics). An explicit
    empty string clears that setting. Every credential field is write-only.
    """

    llm_model: str | None = None
    llm_api_key: str | None = None
    slack_webhook_url: str | None = None
    webhook_url: str | None = None
    webhook_secret: str | None = None
    # Source hosts beyond GitHub.
    gitlab_token: str | None = None
    bitbucket_token: str | None = None
    # Issue trackers.
    jira_url: str | None = None
    jira_email: str | None = None
    jira_api_token: str | None = None
    jira_project_key: str | None = None
    linear_api_key: str | None = None
    linear_team_id: str | None = None


class ProfileUpdate(BaseModel):
    """Change the profile fields a person controls.

    Omitted fields are left alone. Changing the email un-verifies it and sends
    a fresh confirmation link — the new address has not been proven yet, and
    scanning is gated on a verified one.
    """

    display_name: str | None = Field(default=None, max_length=120)
    email: EmailStr | None = None


class PasswordChange(BaseModel):
    """Replace the password, proving the current one first."""

    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


class DeletionBlocker(BaseModel):
    """A condition that stops the account being deleted."""

    code: str
    message: str
    action: str


class DeletionManifestRead(BaseModel):
    """Exactly what deleting this account destroys, counted from real rows.

    The UI renders this itemized rather than as a generic warning: nobody
    should discover what "this cannot be undone" meant afterwards.
    """

    organizations_deleted: list[str] = []
    organizations_left: list[str] = []
    targets: int = 0
    scans: int = 0
    findings: int = 0
    triage_verdicts: int = 0
    api_tokens: int = 0
    share_links: int = 0
    installations: int = 0
    running_scans: int = 0
    blockers: list[DeletionBlocker] = []
    can_delete: bool = True


class AccountDeleteRequest(BaseModel):
    """Confirm deletion.

    ``confirm_email`` must match the account's address: a typed confirmation
    is the difference between deciding and mis-clicking. A password is required
    when the account has one — a hijacked session should not be able to destroy
    six months of scan history.
    """

    confirm_email: EmailStr
    password: str | None = Field(default=None, max_length=128)
