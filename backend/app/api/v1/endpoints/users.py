"""User endpoints."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import UserIntegrationsUpdate, UserRead
from app.services import audit_service, billing_plans, org_service

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(deps.get_current_active_user)) -> User:
    """Return the authenticated user's profile and subscription status."""
    return current_user


@router.post("/me/accept-scan-terms", response_model=UserRead)
def accept_scan_terms(
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(get_db),
) -> User:
    """Record the user's acceptance of the scan-authorization terms.

    Idempotent — keeps the original acceptance timestamp once set.
    """
    if current_user.scan_terms_accepted_at is None:
        current_user.scan_terms_accepted_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(current_user)
    return current_user


@router.patch("/me/integrations", response_model=UserRead)
def update_integrations(
    payload: UserIntegrationsUpdate,
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(get_db),
) -> User:
    """Update integration credentials (PATCH semantics).

    Covers BYOK LLM credentials, Slack, the outbound webhook, the source-host
    tokens for GitLab and Bitbucket, and the Jira/Linear issue trackers. Only
    provided fields change; an empty string clears a field. Setting a BYOK LLM
    model/key requires a plan that allows it (Pro/Enterprise).

    Every value here is a credential, so the audit log records *which* setting
    changed and never what it was set to.
    """
    fields = payload.model_dump(exclude_unset=True)

    if ("llm_api_key" in fields or "llm_model" in fields) and not billing_plans.limits_for(
        current_user.subscription_tier
    ).byok:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "Bring-your-own-key is available on the Pro plan and above.",
                "reason": "byok_not_allowed",
            },
        )

    for name, value in fields.items():
        # Empty string clears; otherwise store the trimmed value.
        setattr(current_user, name, (value.strip() or None) if value else None)

    db.commit()
    db.refresh(current_user)

    org = org_service.ensure_personal_organization(db, current_user)
    audit_service.record(
        db,
        organization_id=org.id,
        action=audit_service.INTEGRATION_UPDATED,
        actor=current_user,
        subject_type="user",
        subject_id=current_user.id,
        detail={"changed": sorted(fields.keys())},
    )
    return current_user
