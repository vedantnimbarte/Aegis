"""Stripe billing: customers, Checkout, the billing portal, webhooks, and the
subscription/quota gate that guards scanning.

Stripe is imported lazily-configured: the secret key is applied per call so a
missing key surfaces as a clean ``BillingError`` (HTTP 400/503) rather than an
import-time crash. All monetary/plan entitlements come from ``billing_plans``.

Entitlement is read from an organization's **billing user** (its owner, or its
agency's owner for a client workspace) while usage is counted across the
*organization*, so a team shares one allowance instead of each member getting
their own.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

import stripe
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.enums import ScanMode, ScanStatus, SubscriptionStatus, SubscriptionTier
from app.models.organization import Organization, OrgMembership
from app.models.scan import Scan
from app.models.target import Target
from app.models.user import User
from app.services import billing_plans, org_service


class BillingError(Exception):
    """Stripe is misconfigured or returned an error."""


class PaymentRequiredError(Exception):
    """The user is not entitled to the requested action (gate/quota).

    ``reason`` is a stable machine code the frontend can branch on
    (``no_subscription`` | ``scan_quota`` | ``target_quota`` | ``seat_quota``).
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


def create_compliance_checkout(db: Session, user: User, scan_id: str) -> str:
    """One-time purchase of an audit-ready compliance pentest report.

    Sold separately from the subscription because it answers a different
    question: not "watch my code" but "give me the document my auditor and my
    prospect's security reviewer will accept", usually against a deadline.
    """
    if not settings.STRIPE_PRICE_COMPLIANCE_REPORT:
        raise BillingError("No Stripe price configured for the compliance report")
    customer_id = get_or_create_customer(db, user)
    session = _stripe().checkout.Session.create(
        mode="payment",
        customer=customer_id,
        line_items=[{"price": settings.STRIPE_PRICE_COMPLIANCE_REPORT, "quantity": 1}],
        success_url=f"{settings.DASHBOARD_URL}/scans/{scan_id}?compliance=purchased",
        cancel_url=f"{settings.DASHBOARD_URL}/scans/{scan_id}",
        client_reference_id=str(user.id),
        metadata={"scan_id": scan_id, "kind": "compliance_report"},
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
    # Seats are the subscription quantity: buying five seats bills five and
    # entitles five, without a second source of truth to drift from Stripe.
    user.purchased_seats = _quantity_from_subscription(subscription)
    user.stripe_subscription_id = subscription.get("id")
    user.subscription_current_period_end = _ts(subscription.get("current_period_end"))
    db.commit()


def _price_from_subscription(subscription: Any) -> Optional[str]:
    items = (subscription.get("items") or {}).get("data") or []
    if not items:
        return None
    return (items[0].get("price") or {}).get("id")


def _quantity_from_subscription(subscription: Any) -> Optional[int]:
    items = (subscription.get("items") or {}).get("data") or []
    if not items:
        return None
    quantity = items[0].get("quantity")
    return quantity if isinstance(quantity, int) and quantity > 0 else None


def _coerce_status(raw: str) -> SubscriptionStatus:
    try:
        return SubscriptionStatus(raw)
    except ValueError:
        return SubscriptionStatus.INCOMPLETE


def _ts(epoch: Any) -> Optional[datetime]:
    if not isinstance(epoch, (int, float)):
        return None
    return datetime.fromtimestamp(epoch, tz=timezone.utc)


# --- Usage counting -------------------------------------------------------
def _first_of_month_utc() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def monthly_credits_used(db: Session, org: Organization) -> int:
    """Scan credits the organization has consumed this UTC month.

    Canceled and failed scans are excluded: charging for a run that produced
    no report is the kind of billing a customer only notices once.
    """
    rows = db.execute(
        select(Scan.scan_mode, Scan.trigger, Scan.status)
        .join(Target, Scan.target_id == Target.id)
        .where(
            Target.organization_id == org.id,
            Scan.created_at >= _first_of_month_utc(),
            Scan.status.notin_((ScanStatus.FAILED, ScanStatus.CANCELED)),
        )
    ).all()
    from app.models.enums import ScanTrigger  # local: avoids a wider import

    return sum(
        billing_plans.credits_for_mode(mode, is_retest=trigger is ScanTrigger.RETEST)
        for mode, trigger, _ in rows
    )


def connected_target_count(db: Session, org: Organization) -> int:
    return db.execute(
        select(func.count(Target.id)).where(Target.organization_id == org.id)
    ).scalar_one()


def seat_count(db: Session, org: Organization) -> int:
    return db.execute(
        select(func.count(OrgMembership.id)).where(
            OrgMembership.organization_id == org.id
        )
    ).scalar_one()


def included_credits(user: User) -> Optional[int]:
    """The organization's credit allowance for the period.

    A purchased override beats the tier default, so a negotiated deal does not
    need a new tier in the code.
    """
    limits = billing_plans.limits_for(user.subscription_tier)
    if user.purchased_scan_credits is not None:
        return user.purchased_scan_credits
    return limits.included_credits


def included_seats(user: User) -> Optional[int]:
    limits = billing_plans.limits_for(user.subscription_tier)
    if user.purchased_seats is not None:
        return user.purchased_seats
    return limits.included_seats


# --- The gate -------------------------------------------------------------
def assert_can_create_scan(
    db: Session,
    org: Organization,
    *,
    scan_mode: ScanMode = ScanMode.QUICK,
    is_retest: bool = False,
) -> None:
    """Raise ``PaymentRequiredError`` unless this organization may scan."""
    payer = org_service.billing_user(db, org)
    if not payer.has_active_subscription:
        raise PaymentRequiredError(
            "An active subscription is required to run scans.", "no_subscription"
        )

    limits = billing_plans.limits_for(payer.subscription_tier)
    cost = billing_plans.credits_for_mode(scan_mode, is_retest=is_retest)
    allowance = included_credits(payer)
    used = monthly_credits_used(db, org)

    if billing_plans.has_credit_for(used, cost, allowance):
        return
    if limits.allow_overage:
        # Past the allowance the plan keeps working and the overage is billed.
        # Failing a customer's pipeline at month-end is worse than an invoice.
        return
    raise PaymentRequiredError(
        f"This scan needs {cost} credit(s) and the {limits.name} plan's "
        f"{allowance} monthly credits are used up. Upgrade for more.",
        "scan_quota",
    )


def assert_can_connect_target(db: Session, org: Organization) -> None:
    """Raise ``PaymentRequiredError`` unless another target may be connected."""
    payer = org_service.billing_user(db, org)
    if not payer.has_active_subscription:
        raise PaymentRequiredError(
            "An active subscription is required to connect targets.",
            "no_subscription",
        )
    limits = billing_plans.limits_for(payer.subscription_tier)
    used = connected_target_count(db, org)
    if not billing_plans.within_limit(used, limits.max_targets):
        raise PaymentRequiredError(
            f"The {limits.name} plan allows {limits.max_targets} targets. "
            "Upgrade to connect more.",
            "target_quota",
        )


def assert_seat_available(db: Session, org: Organization) -> None:
    """Raise ``PaymentRequiredError`` unless another member fits on the plan."""
    payer = org_service.billing_user(db, org)
    allowance = included_seats(payer)
    if billing_plans.within_limit(seat_count(db, org), allowance):
        return
    raise PaymentRequiredError(
        f"Your plan includes {allowance} seats. Add seats to invite more people.",
        "seat_quota",
    )
