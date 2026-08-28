"""Plan definitions and quota math — pure, dependency-free.

Kept free of Stripe/settings/DB imports so the tier limits and quota logic can
be unit-tested in isolation (mirrors the strix_report split).

**Why scans are credits rather than "unlimited".** Every scan spends LLM
tokens, and ``scans.cost_usd`` records exactly how much. An unlimited tier on
a metered engine has no cost floor: one customer running deep scans of a
monorepo hourly costs more than the subscription. So a plan buys a number of
scan credits per period, deep scans cost more credits than quick ones (they
cost us more), and plans that allow overage keep working past the included
allowance instead of failing a build at 3am.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.models.enums import ScanMode, SubscriptionTier

# Stripe subscription statuses that Stripe itself reports and we persist.
STRIPE_ACTIVE_STATUSES = frozenset({"active", "trialing", "past_due"})


# What one scan costs in credits, by depth. Deep scans run longer and spend
# several times the tokens, so charging them the same as a quick scan is
# either a loss on deep or a rip-off on quick.
CREDIT_COST: dict[ScanMode, int] = {
    ScanMode.QUICK: 1,
    ScanMode.STANDARD: 3,
    ScanMode.DEEP: 10,
}

# A retest re-runs a single proof of concept rather than a full survey. It is
# cheap, and charging for it would discourage the verification step that makes
# a "fixed" verdict trustworthy — so it is free.
RETEST_CREDIT_COST = 0


@dataclass(frozen=True)
class PlanLimits:
    """Entitlements for a tier. ``None`` means unlimited."""

    name: str
    max_targets: Optional[int]
    # Scan credits included per billing period (None = unlimited).
    included_credits: Optional[int]
    # Seats included in the base price (None = unlimited).
    included_seats: Optional[int]
    self_serve: bool  # can be purchased via self-serve Stripe Checkout
    byok: bool = False  # may bring their own LLM key (Pro/Enterprise)
    # Whether scanning continues past the included credits (billed as overage)
    # instead of hard-stopping. Off for Starter so a small plan cannot run up
    # a surprise bill.
    allow_overage: bool = False
    # Compliance pack: methodology, control mapping and attestation letter.
    compliance_reports: bool = False
    # White-label report branding, and client workspaces beneath the org.
    white_label: bool = False
    mssp: bool = False


# Source of truth for tier entitlements. Free is the un-subscribed default and
# can never scan; Enterprise is provisioned by sales.
PLAN_LIMITS: dict[SubscriptionTier, PlanLimits] = {
    SubscriptionTier.FREE: PlanLimits(
        "Free",
        max_targets=0,
        included_credits=0,
        included_seats=1,
        self_serve=False,
    ),
    SubscriptionTier.STARTER: PlanLimits(
        "Starter",
        max_targets=3,
        included_credits=20,
        included_seats=2,
        self_serve=True,
    ),
    SubscriptionTier.PRO: PlanLimits(
        "Pro",
        max_targets=None,
        included_credits=200,
        included_seats=10,
        self_serve=True,
        byok=True,
        allow_overage=True,
        compliance_reports=True,
    ),
    SubscriptionTier.ENTERPRISE: PlanLimits(
        "Enterprise",
        max_targets=None,
        included_credits=None,
        included_seats=None,
        self_serve=False,
        byok=True,
        allow_overage=True,
        compliance_reports=True,
        white_label=True,
        mssp=True,
    ),
}


def limits_for(tier: SubscriptionTier) -> PlanLimits:
    return PLAN_LIMITS.get(tier, PLAN_LIMITS[SubscriptionTier.FREE])


def credits_for_mode(scan_mode: ScanMode, is_retest: bool = False) -> int:
    """Credits one scan of this depth consumes."""
    if is_retest:
        return RETEST_CREDIT_COST
    return CREDIT_COST.get(scan_mode, 1)


def within_limit(current: int, limit: Optional[int]) -> bool:
    """Whether one more unit fits under ``limit`` (None = unlimited)."""
    if limit is None:
        return True
    return current < limit


def has_credit_for(used: int, cost: int, included: Optional[int]) -> bool:
    """Whether ``cost`` more credits fit inside the included allowance.

    A free action (a retest) always fits — refusing to verify a fix because
    the month's allowance ran out is exactly backwards.
    """
    if included is None or cost == 0:
        return True
    return used + cost <= included


def remaining(current: int, limit: Optional[int]) -> Optional[int]:
    """Units left before hitting ``limit`` (None = unlimited)."""
    if limit is None:
        return None
    return max(0, limit - current)
