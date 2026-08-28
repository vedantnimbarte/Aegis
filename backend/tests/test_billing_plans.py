"""Tests for the pure plan-limits / quota math (services/billing_plans.py)."""
from __future__ import annotations

from app.models.enums import ScanMode, SubscriptionTier
from app.services import billing_plans as bp


def test_free_tier_cannot_scan_or_connect() -> None:
    limits = bp.limits_for(SubscriptionTier.FREE)
    assert limits.max_targets == 0
    assert limits.included_credits == 0
    assert limits.self_serve is False


def test_starter_is_capped_and_self_serve() -> None:
    limits = bp.limits_for(SubscriptionTier.STARTER)
    assert limits.self_serve is True
    assert isinstance(limits.max_targets, int) and limits.max_targets > 0
    assert isinstance(limits.included_credits, int) and limits.included_credits > 0
    # Starter must never run past its allowance: a small plan that silently
    # bills overage is how a solo developer gets a surprise invoice.
    assert limits.allow_overage is False


def test_pro_has_unlimited_targets_and_metered_credits() -> None:
    limits = bp.limits_for(SubscriptionTier.PRO)
    assert limits.max_targets is None
    assert limits.self_serve is True
    # Credits are bounded even on Pro, because every scan spends real tokens.
    assert isinstance(limits.included_credits, int) and limits.included_credits > 0
    assert limits.allow_overage is True


def test_enterprise_is_unlimited_but_not_self_serve() -> None:
    limits = bp.limits_for(SubscriptionTier.ENTERPRISE)
    assert limits.max_targets is None
    assert limits.included_credits is None
    assert limits.self_serve is False
    assert limits.mssp is True


def test_deeper_scans_cost_more_credits() -> None:
    quick = bp.credits_for_mode(ScanMode.QUICK)
    standard = bp.credits_for_mode(ScanMode.STANDARD)
    deep = bp.credits_for_mode(ScanMode.DEEP)
    assert quick < standard < deep


def test_retests_are_free() -> None:
    # Charging for verification would discourage the step that makes a "fixed"
    # verdict mean anything.
    assert bp.credits_for_mode(ScanMode.DEEP, is_retest=True) == 0


def test_has_credit_for() -> None:
    assert bp.has_credit_for(used=0, cost=3, included=20) is True
    assert bp.has_credit_for(used=18, cost=3, included=20) is False
    assert bp.has_credit_for(used=17, cost=3, included=20) is True  # exactly fits
    assert bp.has_credit_for(used=999, cost=10, included=None) is True  # unlimited
    # A free action always fits, even with the allowance exhausted.
    assert bp.has_credit_for(used=20, cost=0, included=20) is True


def test_within_limit() -> None:
    assert bp.within_limit(0, 3) is True
    assert bp.within_limit(2, 3) is True
    assert bp.within_limit(3, 3) is False  # at the cap -> one more does not fit
    assert bp.within_limit(99, None) is True  # unlimited


def test_remaining() -> None:
    assert bp.remaining(0, 3) == 3
    assert bp.remaining(3, 3) == 0
    assert bp.remaining(5, 3) == 0  # never negative
    assert bp.remaining(10, None) is None  # unlimited
