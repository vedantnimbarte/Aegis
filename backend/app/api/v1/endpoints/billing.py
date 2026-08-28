"""Billing endpoints: Checkout, billing portal, subscription summary, webhook.

Usage is counted per organization while entitlement is read from the
organization's billing user, so a team shares one allowance rather than each
member carrying their own.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.api import deps
from app.api.deps import Principal
from app.core.config import settings
from app.db.session import get_db
from app.models.enums import ScanMode, SubscriptionTier
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
        max_targets=limits.max_targets,
        included_credits=limits.included_credits,
        included_seats=limits.included_seats,
        self_serve=limits.self_serve,
        price_configured=price_configured,
        allow_overage=limits.allow_overage,
        byok=limits.byok,
        compliance_reports=limits.compliance_reports,
        white_label=limits.white_label,
        mssp=limits.mssp,
    )


@router.get("/summary", response_model=BillingSummary)
def billing_summary(
    principal: Principal = Depends(deps.require_viewer),
    db: Session = Depends(get_db),
) -> BillingSummary:
    """Current subscription, usage vs. limits, and the plan catalog."""
    payer = deps.billing_user_for(db, principal)
    org = principal.organization
    return BillingSummary(
        tier=payer.subscription_tier,
        status=payer.subscription_status,
        has_active_subscription=payer.has_active_subscription,
        current_period_end=payer.subscription_current_period_end,
        usage=UsageRead(
            credits_used=billing.monthly_credits_used(db, org),
            credits_included=billing.included_credits(payer),
            connected_targets=billing.connected_target_count(db, org),
            seats_used=billing.seat_count(db, org),
            seats_included=billing.included_seats(payer),
            credit_cost_by_mode={
                mode.value: billing_plans.credits_for_mode(mode) for mode in ScanMode
            },
        ),
        limits=_plan_read(payer.subscription_tier),
        plans=[_plan_read(t) for t in _CATALOG_TIERS],
        # A client workspace spends its agency's plan, so the upgrade button
        # would do nothing there.
        billed_to_parent=org.parent_id is not None,
    )


@router.post("/checkout", response_model=CheckoutResponse)
def create_checkout(
    payload: CheckoutRequest,
    principal: Principal = Depends(deps.require_owner),
    db: Session = Depends(get_db),
) -> CheckoutResponse:
    """Start a Stripe Checkout session to subscribe to a self-serve tier."""
    if principal.user is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Subscriptions are managed by a person, not an API token.",
        )
    try:
        url = billing.create_checkout_session(db, principal.user, payload.tier)
    except billing.BillingError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return CheckoutResponse(checkout_url=url)


@router.post("/compliance-report/{scan_id}", response_model=CheckoutResponse)
def purchase_compliance_report(
    scan_id: uuid.UUID,
    principal: Principal = Depends(deps.require_admin),
    db: Session = Depends(get_db),
) -> CheckoutResponse:
    """Buy a one-off audit-ready compliance report for a completed scan.

    Sold separately from the subscription because it answers a different
    question — "give me the document my auditor will accept" — and usually
    arrives with a deadline attached rather than a monitoring need.
    """
    if principal.user is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Purchases are made by a person, not an API token.",
        )
    from app.services import scan_service

    scan = scan_service.get_scan(db, scan_id, principal.organization)
    if scan is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Scan not found")
    try:
        url = billing.create_compliance_checkout(db, principal.user, str(scan_id))
    except billing.BillingError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return CheckoutResponse(checkout_url=url)


@router.post("/portal", response_model=PortalResponse)
def create_portal(
    principal: Principal = Depends(deps.require_owner),
    db: Session = Depends(get_db),
) -> PortalResponse:
    """Open the Stripe billing portal for managing an existing subscription."""
    if principal.user is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail="Subscriptions are managed by a person, not an API token.",
        )
    try:
        url = billing.create_portal_session(db, principal.user)
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
