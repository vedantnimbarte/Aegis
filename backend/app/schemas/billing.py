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
    max_targets: int | None = None
    included_credits: int | None = None
    included_seats: int | None = None
    self_serve: bool
    price_configured: bool
    allow_overage: bool = False
    byok: bool = False
    compliance_reports: bool = False
    white_label: bool = False
    mssp: bool = False


class UsageRead(BaseModel):
    """What this organization has used against its allowance this period."""

    credits_used: int
    credits_included: int | None = None
    connected_targets: int
    seats_used: int
    seats_included: int | None = None
    # Credits one scan of each depth costs, so the UI can price a scan before
    # the user launches it.
    credit_cost_by_mode: dict[str, int] = {}


class BillingSummary(BaseModel):
    """Everything the dashboard billing page needs in one call."""

    tier: SubscriptionTier
    status: SubscriptionStatus
    has_active_subscription: bool
    current_period_end: datetime | None = None
    usage: UsageRead
    limits: PlanRead
    plans: list[PlanRead]
    # True when the caller is spending someone else's plan (a client
    # workspace billed to its agency), so the UI shows that instead of an
    # upgrade button that would do nothing.
    billed_to_parent: bool = False
