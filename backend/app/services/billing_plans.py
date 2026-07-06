"""Plan definitions and quota math — pure, dependency-free.

Kept free of Stripe/settings/DB imports so the tier limits and quota logic can
be unit-tested in isolation (mirrors the strix_report split).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.models.enums import SubscriptionTier

# Stripe subscription statuses that Stripe itself reports and we persist.
STRIPE_ACTIVE_STATUSES = frozenset({"active", "trialing", "past_due"})


@dataclass(frozen=True)
class PlanLimits:
    """Usage caps for a tier. ``None`` means unlimited."""

    name: str
    max_repos: Optional[int]
    monthly_scans: Optional[int]
    self_serve: bool  # can be purchased via self-serve Stripe Checkout


# Source of truth for tier entitlements (see PRD §6). Free is the un-subscribed
# default and can never scan; Enterprise is provisioned by sales.
PLAN_LIMITS: dict[SubscriptionTier, PlanLimits] = {
    SubscriptionTier.FREE: PlanLimits("Free", max_repos=0, monthly_scans=0, self_serve=False),
    SubscriptionTier.STARTER: PlanLimits("Starter", max_repos=3, monthly_scans=20, self_serve=True),
    SubscriptionTier.PRO: PlanLimits("Pro", max_repos=None, monthly_scans=None, self_serve=True),
    SubscriptionTier.ENTERPRISE: PlanLimits("Enterprise", max_repos=None, monthly_scans=None, self_serve=False),
}


def limits_for(tier: SubscriptionTier) -> PlanLimits:
    return PLAN_LIMITS.get(tier, PLAN_LIMITS[SubscriptionTier.FREE])


def within_limit(current: int, limit: Optional[int]) -> bool:
    """Whether one more unit fits under ``limit`` (None = unlimited)."""
    if limit is None:
        return True
    return current < limit


def remaining(current: int, limit: Optional[int]) -> Optional[int]:
    """Units left before hitting ``limit`` (None = unlimited)."""
    if limit is None:
        return None
    return max(0, limit - current)
