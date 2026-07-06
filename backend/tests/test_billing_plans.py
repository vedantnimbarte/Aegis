"""Tests for the pure plan-limits / quota math (services/billing_plans.py)."""
from __future__ import annotations

from app.models.enums import SubscriptionTier
from app.services import billing_plans as bp


def test_free_tier_cannot_scan_or_connect() -> None:
    limits = bp.limits_for(SubscriptionTier.FREE)
    assert limits.max_repos == 0
    assert limits.monthly_scans == 0
    assert limits.self_serve is False


def test_starter_is_capped_and_self_serve() -> None:
    limits = bp.limits_for(SubscriptionTier.STARTER)
    assert limits.self_serve is True
    assert isinstance(limits.max_repos, int) and limits.max_repos > 0
    assert isinstance(limits.monthly_scans, int) and limits.monthly_scans > 0


def test_pro_is_unlimited() -> None:
    limits = bp.limits_for(SubscriptionTier.PRO)
    assert limits.max_repos is None
    assert limits.monthly_scans is None
    assert limits.self_serve is True


def test_enterprise_is_unlimited_but_not_self_serve() -> None:
    limits = bp.limits_for(SubscriptionTier.ENTERPRISE)
    assert limits.max_repos is None
    assert limits.self_serve is False


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
