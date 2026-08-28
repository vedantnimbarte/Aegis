"""Organization endpoints: teams, roles, audit log, API tokens.

The organization a request acts in comes from the ``X-Aegis-Org`` header (a
UUID or a slug); without it the caller acts in their own organization, so a
single-team customer never has to think about it.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.api.deps import Principal
from app.db.session import get_db
from app.models.enums import ROLE_RANK, OrgRole
from app.models.user import User
from app.schemas.organization import (
    ApiTokenCreate,
    ApiTokenCreated,
    ApiTokenRead,
    AuditEventRead,
    MemberInvite,
    MemberRead,
    MemberRoleUpdate,
    OrganizationCreate,
    OrganizationRead,
    OrganizationUpdate,
)
from app.services import (
    api_token_service,
    audit_service,
    billing,
    billing_plans,
    org_service,
    user_service,
)

router = APIRouter(prefix="/orgs", tags=["organizations"])


def _read(org, role: OrgRole | None = None) -> OrganizationRead:
    out = OrganizationRead.model_validate(org)
    out.role = role
    out.is_client_workspace = org.parent_id is not None
    return out


@router.get("", response_model=list[OrganizationRead])
def list_organizations(
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(get_db),
) -> list[OrganizationRead]:
    """Every organization the signed-in user belongs to.

    Creates their personal one on first call, so a user who predates
    organizations still lands somewhere.
    """
    org_service.ensure_personal_organization(db, current_user)
    return [
        _read(org, org_service.role_in(db, org, current_user))
        for org in org_service.list_organizations(db, current_user)
    ]


@router.post("", response_model=OrganizationRead, status_code=status.HTTP_201_CREATED)
def create_organization(
    payload: OrganizationCreate,
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(get_db),
) -> OrganizationRead:
    """Create an organization, or a client workspace beneath one you administer.

    Client workspaces are the agency/MSSP model: they bill to the parent and
    the parent's admins can operate them, so creating one requires admin on
    the parent and a plan that includes the feature.
    """
    parent = None
    if payload.parent_id is not None:
        parent = org_service.get_organization(db, payload.parent_id, current_user)
        if parent is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Organization not found")
        if not org_service.has_role(db, parent, current_user, OrgRole.ADMIN):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail={
                    "message": "Creating a client workspace requires the admin role.",
                    "reason": "insufficient_role",
                },
            )
        payer = org_service.billing_user(db, parent)
        if not billing_plans.limits_for(payer.subscription_tier).mssp:
            raise HTTPException(
                status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "message": "Client workspaces are an Enterprise feature.",
                    "reason": "plan_feature",
                },
            )

    org = org_service.create_organization(
        db, name=payload.name, owner=current_user, parent=parent
    )
    audit_service.record(
        db,
        organization_id=org.id,
        action=audit_service.ORG_CREATED,
        actor=current_user,
        subject_type="organization",
        subject_id=org.id,
        detail={"name": org.name, "parent": str(parent.id) if parent else None},
    )
    return _read(org, OrgRole.OWNER)


@router.get("/current", response_model=OrganizationRead)
def get_current_organization(
    principal: Principal = Depends(deps.require_viewer),
) -> OrganizationRead:
    """The organization this request is acting in, and the caller's role in it."""
    return _read(principal.organization, principal.role)


@router.patch("/current", response_model=OrganizationRead)
def update_organization(
    payload: OrganizationUpdate,
    principal: Principal = Depends(deps.require_admin),
    db: Session = Depends(get_db),
) -> OrganizationRead:
    """Rename the organization, or set its report branding."""
    org = principal.organization
    changes = payload.model_dump(exclude_unset=True)

    if {"brand_name", "brand_primary_color"} & set(changes):
        payer = deps.billing_user_for(db, principal)
        if not billing_plans.limits_for(payer.subscription_tier).white_label:
            raise HTTPException(
                status.HTTP_402_PAYMENT_REQUIRED,
                detail={
                    "message": "Report branding is an Enterprise feature.",
                    "reason": "plan_feature",
                },
            )

    for field, value in changes.items():
        setattr(org, field, value)
    db.commit()
    db.refresh(org)
    return _read(org, principal.role)


# --- Members --------------------------------------------------------------
@router.get("/current/members", response_model=list[MemberRead])
def list_members(
    principal: Principal = Depends(deps.require_viewer),
    db: Session = Depends(get_db),
) -> list[MemberRead]:
    return [
        MemberRead(
            id=m.id,
            user_id=m.user_id,
            email=m.user.email,
            role=m.role,
            created_at=m.created_at,
        )
        for m in org_service.list_members(db, principal.organization)
    ]


@router.post(
    "/current/members", response_model=MemberRead, status_code=status.HTTP_201_CREATED
)
def add_member(
    payload: MemberInvite,
    principal: Principal = Depends(deps.require_admin),
    db: Session = Depends(get_db),
) -> MemberRead:
    """Give an existing Aegis account a seat in this organization."""
    if ROLE_RANK[payload.role] > ROLE_RANK[principal.role]:
        # Otherwise an admin could mint an owner and then be removed by them.
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={
                "message": "You cannot grant a role above your own.",
                "reason": "insufficient_role",
            },
        )

    user = user_service.get_user_by_email(db, str(payload.email).strip().lower())
    if user is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=(
                "No Aegis account exists for that address. Ask them to sign up "
                "first, then add them here."
            ),
        )

    try:
        billing.assert_seat_available(db, principal.organization)
    except billing.PaymentRequiredError as exc:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            detail={"message": exc.detail, "reason": exc.reason},
        )

    membership = org_service.add_member(db, principal.organization, user, payload.role)
    audit_service.record(
        db,
        organization_id=principal.organization.id,
        action=audit_service.MEMBER_ADDED,
        actor=principal.user,
        subject_type="user",
        subject_id=user.id,
        detail={"email": user.email, "role": payload.role.value},
    )
    return MemberRead(
        id=membership.id,
        user_id=user.id,
        email=user.email,
        role=membership.role,
        created_at=membership.created_at,
    )


@router.patch("/current/members/{membership_id}", response_model=MemberRead)
def update_member_role(
    membership_id: uuid.UUID,
    payload: MemberRoleUpdate,
    principal: Principal = Depends(deps.require_admin),
    db: Session = Depends(get_db),
) -> MemberRead:
    membership = org_service.get_membership(db, principal.organization, membership_id)
    if membership is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Member not found")
    if ROLE_RANK[payload.role] > ROLE_RANK[principal.role]:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={
                "message": "You cannot grant a role above your own.",
                "reason": "insufficient_role",
            },
        )

    previous = membership.role
    membership.role = payload.role
    db.commit()
    db.refresh(membership)
    audit_service.record(
        db,
        organization_id=principal.organization.id,
        action=audit_service.MEMBER_ROLE_CHANGED,
        actor=principal.user,
        subject_type="user",
        subject_id=membership.user_id,
        detail={"from": previous.value, "to": payload.role.value},
    )
    return MemberRead(
        id=membership.id,
        user_id=membership.user_id,
        email=membership.user.email,
        role=membership.role,
        created_at=membership.created_at,
    )


@router.delete(
    "/current/members/{membership_id}", status_code=status.HTTP_204_NO_CONTENT
)
def remove_member(
    membership_id: uuid.UUID,
    principal: Principal = Depends(deps.require_admin),
    db: Session = Depends(get_db),
):
    membership = org_service.get_membership(db, principal.organization, membership_id)
    if membership is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Member not found")

    email = membership.user.email
    user_id = membership.user_id
    if not org_service.remove_member(db, membership):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail=(
                "This is the organization's last owner. Promote another member "
                "to owner before removing them."
            ),
        )
    audit_service.record(
        db,
        organization_id=principal.organization.id,
        action=audit_service.MEMBER_REMOVED,
        actor=principal.user,
        subject_type="user",
        subject_id=user_id,
        detail={"email": email},
    )


# --- Audit log ------------------------------------------------------------
@router.get("/current/audit", response_model=list[AuditEventRead])
def list_audit_events(
    action: str | None = None,
    limit: int = 200,
    principal: Principal = Depends(deps.require_admin),
    db: Session = Depends(get_db),
) -> list[AuditEventRead]:
    """Who did what in this organization, newest first.

    Admin-only: the log names people and the targets they touched, which is
    not something an ordinary member needs.
    """
    return [
        AuditEventRead.model_validate(event)
        for event in audit_service.list_events(
            db, principal.organization, action=action, limit=limit
        )
    ]


# --- API tokens -----------------------------------------------------------
@router.get("/current/tokens", response_model=list[ApiTokenRead])
def list_tokens(
    principal: Principal = Depends(deps.require_admin),
    db: Session = Depends(get_db),
) -> list[ApiTokenRead]:
    return [
        ApiTokenRead.model_validate(t)
        for t in api_token_service.list_tokens(db, principal.organization)
    ]


@router.post(
    "/current/tokens", response_model=ApiTokenCreated, status_code=status.HTTP_201_CREATED
)
def create_token(
    payload: ApiTokenCreate,
    principal: Principal = Depends(deps.require_admin),
    db: Session = Depends(get_db),
) -> ApiTokenCreated:
    """Issue an API token for CI or a script.

    The plaintext is returned once and never again — only its digest is
    stored, so a leaked database cannot be used to attack the customer's
    production systems.
    """
    if ROLE_RANK[payload.role] > ROLE_RANK[principal.role]:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            detail={
                "message": "You cannot issue a token with a role above your own.",
                "reason": "insufficient_role",
            },
        )

    token, plaintext = api_token_service.issue(
        db,
        org=principal.organization,
        creator=principal.user,
        name=payload.name,
        role=payload.role,
        expires_in_days=payload.expires_in_days,
    )
    audit_service.record(
        db,
        organization_id=principal.organization.id,
        action=audit_service.TOKEN_CREATED,
        actor=principal.user,
        subject_type="api_token",
        subject_id=token.id,
        detail={"name": token.name, "role": token.role.value},
    )
    read = ApiTokenRead.model_validate(token)
    return ApiTokenCreated(**read.model_dump(), token=plaintext)


@router.delete(
    "/current/tokens/{token_id}", status_code=status.HTTP_204_NO_CONTENT
)
def revoke_token(
    token_id: uuid.UUID,
    principal: Principal = Depends(deps.require_admin),
    db: Session = Depends(get_db),
):
    token = api_token_service.get_token(db, principal.organization, token_id)
    if token is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Token not found")
    api_token_service.revoke(db, token)
    audit_service.record(
        db,
        organization_id=principal.organization.id,
        action=audit_service.TOKEN_REVOKED,
        actor=principal.user,
        subject_type="api_token",
        subject_id=token.id,
        detail={"name": token.name},
    )
