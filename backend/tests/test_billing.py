"""Tests for billing service helpers that don't require Stripe or a DB."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.core.config import settings
from app.models.enums import SubscriptionStatus, SubscriptionTier
from app.models.user import User
from app.services import billing


@pytest.fixture(autouse=True)
def _prices(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "STRIPE_PRICE_STARTER", "price_starter", raising=False)
    monkeypatch.setattr(settings, "STRIPE_PRICE_PRO", "price_pro", raising=False)


def test_tier_for_price_roundtrip() -> None:
    assert billing.tier_for_price("price_starter") is SubscriptionTier.STARTER
    assert billing.tier_for_price("price_pro") is SubscriptionTier.PRO
    assert billing.tier_for_price("price_unknown") is None
    assert billing.tier_for_price(None) is None


def test_price_for_tier() -> None:
    assert billing._price_for_tier(SubscriptionTier.STARTER) == "price_starter"
    assert billing._price_for_tier(SubscriptionTier.PRO) == "price_pro"


def test_price_for_enterprise_raises() -> None:
    with pytest.raises(billing.BillingError):
        billing._price_for_tier(SubscriptionTier.ENTERPRISE)


def test_ts_conversion() -> None:
    dt = billing._ts(0)
    assert dt == datetime(1970, 1, 1, tzinfo=timezone.utc)
    assert billing._ts(None) is None
    assert billing._ts("nope") is None


def test_coerce_status() -> None:
    assert billing._coerce_status("active") is SubscriptionStatus.ACTIVE
    assert billing._coerce_status("past_due") is SubscriptionStatus.PAST_DUE
    assert billing._coerce_status("weird") is SubscriptionStatus.INCOMPLETE


def _user(**kwargs) -> User:
    u = User(email="a@b.com")
    u.subscription_status = kwargs.get("status", SubscriptionStatus.NONE)
    u.subscription_current_period_end = kwargs.get("period_end")
    return u


def test_has_active_subscription() -> None:
    future = datetime.now(timezone.utc) + timedelta(days=5)
    past = datetime.now(timezone.utc) - timedelta(days=5)

    assert _user(status=SubscriptionStatus.NONE).has_active_subscription is False
    assert _user(status=SubscriptionStatus.CANCELED).has_active_subscription is False
    assert _user(status=SubscriptionStatus.ACTIVE, period_end=future).has_active_subscription is True
    assert _user(status=SubscriptionStatus.TRIALING).has_active_subscription is True
    # past_due still counts (grace window before Stripe cancels).
    assert _user(status=SubscriptionStatus.PAST_DUE, period_end=future).has_active_subscription is True
    # Active but the paid period already lapsed -> not active.
    assert _user(status=SubscriptionStatus.ACTIVE, period_end=past).has_active_subscription is False
