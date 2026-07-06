"""Stripe billing: customers, Checkout, the billing portal, webhooks, and the
subscription/quota gate that guards scanning.

Stripe is imported lazily-configured: the secret key is applied per call so a
missing key surfaces as a clean ``BillingError`` (HTTP 400/503) rather than an
import-time crash. All monetary/plan entitlements come from ``billing_plans``.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

import stripe
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.enums import SubscriptionStatus, SubscriptionTier
from app.models.repository import Repository
from app.models.scan import Scan
from app.models.user import User
from app.services import billing_plans


class BillingError(Exception):
    """Stripe is misconfigured or returned an error."""


class PaymentRequiredError(Exception):
    """The user is not entitled to the requested action (gate/quota).

    ``reason`` is a stable machine code the frontend can branch on
    (``no_subscription`` | ``scan_quota`` | ``repo_quota``).
    """

    def __init__(self, detail: str, reason: str) -> None:
        super().__init__(detail)
        self.detail = detail
        self.reason = reason


# --- Stripe plumbing ------------------------------------------------------
def _stripe() -> Any:
    """Return the configured stripe module, or raise if no key is set."""
    if not settings.STRIPE_SECRET_KEY:
        raise BillingError("Stripe is not configured on the server")
    stripe.api_key = settings.STRIPE_SECRET_KEY
    return stripe


def _price_for_tier(tier: SubscriptionTier) -> str:
    price = {
        SubscriptionTier.STARTER: settings.STRIPE_PRICE_STARTER,
        SubscriptionTier.PRO: settings.STRIPE_PRICE_PRO,
    }.get(tier, "")
    if not price:
        raise BillingError(f"No Stripe price configured for the {tier.value} plan")
    return price


def tier_for_price(price_id: Optional[str]) -> Optional[SubscriptionTier]:
    """Reverse-map a Stripe price id back to a tier (None if unrecognized)."""
    if not price_id:
        return None
    mapping = {
        settings.STRIPE_PRICE_STARTER: SubscriptionTier.STARTER,
        settings.STRIPE_PRICE_PRO: SubscriptionTier.PRO,
    }
    return mapping.get(price_id)


# --- Customer / Checkout / Portal ----------------------------------------
def get_or_create_customer(db: Session, user: User) -> str:
    """Return the user's Stripe customer id, creating the customer if needed."""
    if user.stripe_customer_id:
        return user.stripe_customer_id

    customer = _stripe().Customer.create(
        email=user.email,
        metadata={"user_id": str(user.id)},
    )
    user.stripe_customer_id = customer["id"]
    db.commit()
    db.refresh(user)
    return customer["id"]


def create_checkout_session(db: Session, user: User, tier: SubscriptionTier) -> str:
    """Create a subscription Checkout session and return its URL."""
    if not billing_plans.limits_for(tier).self_serve:
        raise BillingError(
            f"The {tier.value} plan is not available for self-serve checkout"
        )
    price_id = _price_for_tier(tier)
    customer_id = get_or_create_customer(db, user)

    session = _stripe().checkout.Session.create(
        mode="subscription",
        customer=customer_id,
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{settings.DASHBOARD_URL}/billing?checkout=success",
        cancel_url=f"{settings.DASHBOARD_URL}/billing?checkout=cancelled",
        client_reference_id=str(user.id),
        allow_promotion_codes=True,
    )
    if not session.get("url"):
        raise BillingError("Stripe did not return a checkout URL")
    return session["url"]


def create_portal_session(db: Session, user: User) -> str:
    """Create a billing-portal session so the user can manage their plan."""
    if not user.stripe_customer_id:
        raise BillingError("No billing account exists for this user yet")
    session = _stripe().billing_portal.Session.create(
        customer=user.stripe_customer_id,
        return_url=f"{settings.DASHBOARD_URL}/billing",
    )
    return session["url"]


# --- Webhooks -------------------------------------------------------------
def construct_event(payload: bytes, sig_header: Optional[str]) -> Any:
    """Verify a webhook payload's signature and return the Stripe event."""
    if not settings.STRIPE_WEBHOOK_SECRET:
        raise BillingError("Stripe webhook secret is not configured")
    try:
        return stripe.Webhook.construct_event(
            payload, sig_header or "", settings.STRIPE_WEBHOOK_SECRET
        )
    except ValueError as exc:  # malformed payload
        raise BillingError("Invalid webhook payload") from exc
    except stripe.error.SignatureVerificationError as exc:
        raise BillingError("Invalid webhook signature") from exc


def handle_event(db: Session, event: Any) -> None:
    """Apply a verified Stripe event to our subscription state."""
    event_type = event.get("type", "")
    obj = event.get("data", {}).get("object", {})

    if event_type == "checkout.session.completed":
        sub_id = obj.get("subscription")
        if sub_id:
            subscription = _stripe().Subscription.retrieve(sub_id)
            _apply_subscription(db, subscription)
    elif event_type in (
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    ):
        _apply_subscription(db, obj)


def _apply_subscription(db: Session, subscription: Any) -> None:
    """Sync a Stripe subscription object onto the owning user."""
    customer_id = subscription.get("customer")
    user = (
        db.execute(select(User).where(User.stripe_customer_id == customer_id))
        .scalar_one_or_none()
        if customer_id
        else None
    )
    if user is None:
        return  # unknown customer — nothing to update

    status_raw = subscription.get("status", "")

    # A canceled/ended subscription drops the user back to the free tier.
    if status_raw == "canceled":
        user.subscription_status = SubscriptionStatus.CANCELED
        user.subscription_tier = SubscriptionTier.FREE
        user.subscription_current_period_end = _ts(subscription.get("current_period_end"))
        db.commit()
        return

    user.subscription_status = _coerce_status(status_raw)
    price_id = _price_from_subscription(subscription)
    tier = tier_for_price(price_id)
    if tier is not None:
        user.subscription_tier = tier
    user.stripe_subscription_id = subscription.get("id")
    user.subscription_current_period_end = _ts(subscription.get("current_period_end"))
    db.commit()


def _price_from_subscription(subscription: Any) -> Optional[str]:
    items = (subscription.get("items") or {}).get("data") or []
    if not items:
        return None
    return (items[0].get("price") or {}).get("id")


def _coerce_status(raw: str) -> SubscriptionStatus:
    try:
        return SubscriptionStatus(raw)
    except ValueError:
        return SubscriptionStatus.INCOMPLETE


def _ts(epoch: Any) -> Optional[datetime]:
    if not isinstance(epoch, (int, float)):
        return None
    return datetime.fromtimestamp(epoch, tz=timezone.utc)


# --- The gate -------------------------------------------------------------
def _first_of_month_utc() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def monthly_scan_count(db: Session, user: User) -> int:
    """Scans the user has created since the start of the current UTC month."""
    return db.execute(
        select(func.count(Scan.id))
        .select_from(Scan)
        .join(Repository, Scan.repository_id == Repository.id)
        .where(Repository.user_id == user.id, Scan.created_at >= _first_of_month_utc())
    ).scalar_one()


def connected_repo_count(db: Session, user: User) -> int:
    return db.execute(
        select(func.count(Repository.id)).where(Repository.user_id == user.id)
    ).scalar_one()


def assert_can_create_scan(db: Session, user: User) -> None:
    """Raise ``PaymentRequiredError`` unless the user may launch another scan."""
    if not user.has_active_subscription:
        raise PaymentRequiredError(
            "An active subscription is required to run scans.", "no_subscription"
        )
    limits = billing_plans.limits_for(user.subscription_tier)
    used = monthly_scan_count(db, user)
    if not billing_plans.within_limit(used, limits.monthly_scans):
        raise PaymentRequiredError(
            f"You've used all {limits.monthly_scans} scans on the {limits.name} plan "
            "this month. Upgrade for more.",
            "scan_quota",
        )


def assert_can_connect_repo(db: Session, user: User) -> None:
    """Raise ``PaymentRequiredError`` unless the user may connect another repo."""
    if not user.has_active_subscription:
        raise PaymentRequiredError(
            "An active subscription is required to connect repositories.",
            "no_subscription",
        )
    limits = billing_plans.limits_for(user.subscription_tier)
    used = connected_repo_count(db, user)
    if not billing_plans.within_limit(used, limits.max_repos):
        raise PaymentRequiredError(
            f"The {limits.name} plan allows {limits.max_repos} repositories. "
            "Upgrade to connect more.",
            "repo_quota",
        )
