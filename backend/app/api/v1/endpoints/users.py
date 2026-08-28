"""User endpoints."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.core import security
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.user import (
    AccountDeleteRequest,
    DeletionManifestRead,
    PasswordChange,
    ProfileUpdate,
    UserIntegrationsUpdate,
    UserRead,
)
from app.services import (
    account_service,
    audit_service,
    billing_plans,
    org_service,
    user_service,
)
from app.services import email as email_service

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


# --- Profile ---------------------------------------------------------------
@router.patch("/me", response_model=UserRead)
def update_profile(
    payload: ProfileUpdate,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(get_db),
) -> User:
    """Change the profile fields a person controls.

    Changing the email address un-verifies it and sends a fresh confirmation
    link: the new address has not been proven, and scanning is gated on a
    verified one.
    """
    fields = payload.model_dump(exclude_unset=True)
    new_email = fields.get("email")

    if new_email:
        normalized = str(new_email).strip().lower()
        if normalized != current_user.email:
            taken = user_service.get_user_by_email(db, normalized)
            if taken is not None:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    detail="That email address is already in use.",
                )

    user, email_changed = account_service.update_profile(
        db,
        current_user,
        display_name=fields.get("display_name") if "display_name" in fields else None,
        email=str(new_email) if new_email else None,
    )

    if email_changed:
        token = security.create_email_verification_token(user.id)
        background_tasks.add_task(
            email_service.send_verification_email,
            user.email,
            f"{settings.DASHBOARD_URL}/verify-email?token={token}",
        )

    org = org_service.ensure_personal_organization(db, user)
    audit_service.record(
        db,
        organization_id=org.id,
        action=audit_service.PROFILE_UPDATED,
        actor=user,
        subject_type="user",
        subject_id=user.id,
        detail={"changed": sorted(fields.keys()), "email_changed": email_changed},
    )
    return user


@router.post("/me/password", response_model=UserRead)
def change_password(
    payload: PasswordChange,
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(get_db),
) -> User:
    """Set a new password, proving the current one first."""
    try:
        user = account_service.change_password(
            db,
            current_user,
            current=payload.current_password,
            new=payload.new_password,
        )
    except account_service.PasswordError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))

    org = org_service.ensure_personal_organization(db, user)
    audit_service.record(
        db,
        organization_id=org.id,
        action=audit_service.PASSWORD_CHANGED,
        actor=user,
        subject_type="user",
        subject_id=user.id,
    )
    return user


# --- Deletion --------------------------------------------------------------
@router.get("/me/deletion-manifest", response_model=DeletionManifestRead)
def deletion_manifest(
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(get_db),
) -> DeletionManifestRead:
    """What deleting this account would destroy, and what stops it.

    Counted from the real rows so the confirmation screen states facts rather
    than a generic warning.
    """
    manifest = account_service.deletion_manifest(db, current_user)
    return DeletionManifestRead(
        organizations_deleted=manifest.organizations_deleted,
        organizations_left=manifest.organizations_left,
        targets=manifest.targets,
        scans=manifest.scans,
        findings=manifest.findings,
        triage_verdicts=manifest.triage_verdicts,
        api_tokens=manifest.api_tokens,
        share_links=manifest.share_links,
        installations=manifest.installations,
        running_scans=manifest.running_scans,
        blockers=[vars(b) for b in manifest.blockers],
        can_delete=manifest.can_delete,
    )


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    payload: AccountDeleteRequest,
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(get_db),
):
    """Delete the account and everything that belongs to it alone.

    Three things have to line up: the typed address matches, the password
    verifies (when the account has one), and no blocker stands. The manifest is
    re-checked here rather than trusted from the client — the screen the user
    confirmed may be minutes stale, and someone may have joined their
    organization since.
    """
    if str(payload.confirm_email).strip().lower() != current_user.email:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="That does not match the email address on this account.",
        )

    if current_user.hashed_password:
        if not payload.password or not security.verify_password(
            payload.password, current_user.hashed_password
        ):
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                detail="Enter your password to confirm.",
            )

    manifest = account_service.deletion_manifest(db, current_user)
    if not manifest.can_delete:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail={
                "message": manifest.blockers[0].message,
                "reason": manifest.blockers[0].code,
                "action": manifest.blockers[0].action,
            },
        )

    account_service.delete_account(db, current_user)
