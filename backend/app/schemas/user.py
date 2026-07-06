"""User response schemas.

Note: `github_token` and `hashed_password` are deliberately never exposed.
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
