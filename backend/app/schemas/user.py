"""User response schemas.

Note: tokens, API keys and `hashed_password` are deliberately never exposed —
reads return only booleans saying whether each is configured.
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import SubscriptionStatus, SubscriptionTier


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    email_verified: bool
    github_username: str | None = None
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
