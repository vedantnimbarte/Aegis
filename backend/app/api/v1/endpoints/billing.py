"""Billing endpoints: Checkout, billing portal, subscription summary, webhook."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api import deps
from app.core.config import settings
from app.db.session import get_db
from app.models.enums import SubscriptionTier
from app.models.user import User
from app.schemas.billing import (
    BillingSummary,
    CheckoutRequest,
    CheckoutResponse,
    PlanRead,
    PortalResponse,
    UsageRead,
)
from app.services import billing, billing_plans

router = APIRouter(prefix="/billing", tags=["billing"])

# Tiers advertised on the billing page (Free is the un-subscribed default).
_CATALOG_TIERS = [SubscriptionTier.STARTER, SubscriptionTier.PRO, SubscriptionTier.ENTERPRISE]


def _plan_read(tier: SubscriptionTier) -> PlanRead:
    limits = billing_plans.limits_for(tier)
    price_configured = (
        tier == SubscriptionTier.STARTER and bool(settings.STRIPE_PRICE_STARTER)
    ) or (tier == SubscriptionTier.PRO and bool(settings.STRIPE_PRICE_PRO))
    return PlanRead(
        tier=tier,
        name=limits.name,
        max_repos=limits.max_repos,
        monthly_scans=limits.monthly_scans,
        self_serve=limits.self_serve,
        price_configured=price_configured,
    )


@router.get("/summary", response_model=BillingSummary)
def billing_summary(
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(get_db),
) -> BillingSummary:
    """Current subscription, usage vs. limits, and the plan catalog."""
    return BillingSummary(
        tier=current_user.subscription_tier,
        status=current_user.subscription_status,
        has_active_subscription=current_user.has_active_subscription,
        current_period_end=current_user.subscription_current_period_end,
        usage=UsageRead(
            scans_this_month=billing.monthly_scan_count(db, current_user),
            connected_repos=billing.connected_repo_count(db, current_user),
        ),
        limits=_plan_read(current_user.subscription_tier),
        plans=[_plan_read(t) for t in _CATALOG_TIERS],
    )


@router.post("/checkout", response_model=CheckoutResponse)
def create_checkout(
    payload: CheckoutRequest,
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(get_db),
) -> CheckoutResponse:
    """Start a Stripe Checkout session to subscribe to a self-serve tier."""
    try:
        url = billing.create_checkout_session(db, current_user, payload.tier)
    except billing.BillingError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return CheckoutResponse(checkout_url=url)


@router.post("/portal", response_model=PortalResponse)
def create_portal(
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(get_db),
) -> PortalResponse:
    """Open the Stripe billing portal for managing an existing subscription."""
    try:
        url = billing.create_portal_session(db, current_user)
    except billing.BillingError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return PortalResponse(portal_url=url)


@router.post("/webhook", include_in_schema=False)
async def stripe_webhook(request: Request, db: Session = Depends(get_db)) -> dict:
    """Receive and process Stripe webhook events (signature-verified)."""
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")
    try:
        event = billing.construct_event(payload, sig_header)
    except billing.BillingError as exc:
        # 400 tells Stripe the delivery failed so it will retry.
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))

    billing.handle_event(db, event)
    return {"received": True}
