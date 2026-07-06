"""Billing request/response schemas."""
from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.models.enums import SubscriptionStatus, SubscriptionTier


class CheckoutRequest(BaseModel):
    """Which tier to subscribe to (self-serve tiers only)."""

    tier: SubscriptionTier


class CheckoutResponse(BaseModel):
    checkout_url: str


class PortalResponse(BaseModel):
    portal_url: str


class PlanRead(BaseModel):
    """A tier's entitlements, for rendering plan cards / current limits."""

    tier: SubscriptionTier
    name: str
    max_repos: int | None = None
    monthly_scans: int | None = None
    self_serve: bool
    price_configured: bool


class UsageRead(BaseModel):
    scans_this_month: int
    connected_repos: int


class BillingSummary(BaseModel):
    """Everything the dashboard billing page needs in one call."""

    tier: SubscriptionTier
    status: SubscriptionStatus
    has_active_subscription: bool
    current_period_end: datetime | None = None
    usage: UsageRead
    limits: PlanRead
    plans: list[PlanRead]
