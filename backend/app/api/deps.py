"""Reusable FastAPI dependencies: authentication, organization, and role.

Two credentials reach the same place. A user's JWT resolves to a person; an
API token (``aeg_…``) resolves to an organization plus the role that token was
issued with. Both end up as a ``Principal``, so every endpoint below the
dependency is written once and works for a human and for CI alike.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Optional

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core import security
from app.db.session import get_db
from app.models.enums import ROLE_RANK, OrgRole
from app.models.organization import Organization
from app.models.user import User
from app.services import api_token_service, org_service, user_service

# `Authorization: Bearer <token>` — surfaces an "Authorize" button in /docs.
bearer_scheme = HTTPBearer(auto_error=True)

_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


@dataclass
class Principal:
    """Who is acting, and with what authority.

    ``user`` is present for a human request and for a token (the token's
    creator is not the actor, so it stays None). ``organization`` is always
    resolved; ``role`` is the effective role in that organization.
    """

    organization: Organization
    role: OrgRole
    user: Optional[User] = None
    via_token: bool = False

    @property
    def actor(self) -> Optional[User]:
        """The human to attribute an audit event to, if there is one."""
        return self.user


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the authenticated user from a bearer *access* token."""
    try:
        payload = security.decode_token(credentials.credentials)
    except JWTError:
        raise _CREDENTIALS_EXCEPTION

    # Reject refresh tokens (or anything not minted as an access token).
    if payload.get("type") != security.ACCESS_TOKEN_TYPE:
        raise _CREDENTIALS_EXCEPTION

    subject = payload.get("sub")
    if not subject:
        raise _CREDENTIALS_EXCEPTION

    user = user_service.get_user_by_id(db, subject)
    if user is None:
        raise _CREDENTIALS_EXCEPTION
    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user"
        )
    return current_user


# --- Organization resolution ---------------------------------------------
def _lookup_org(db: Session, reference: str) -> Optional[Organization]:
    """Resolve an ``X-Aegis-Org`` value, which may be a UUID or a slug."""
    from sqlalchemy import select  # local: keeps the module's imports flat

    try:
        return db.get(Organization, uuid.UUID(reference))
    except (ValueError, TypeError):
        return db.execute(
            select(Organization).where(Organization.slug == reference)
        ).scalar_one_or_none()


def get_principal(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    x_aegis_org: Optional[str] = Header(default=None, alias="X-Aegis-Org"),
    db: Session = Depends(get_db),
) -> Principal:
    """Resolve the caller into an organization plus a role.

    A JWT without ``X-Aegis-Org`` acts in the user's own organization, which
    keeps single-team customers from ever having to think about the header.
    """
    raw = credentials.credentials

    # --- API token path ---------------------------------------------------
    if raw.startswith(api_token_service.TOKEN_PREFIX):
        token = api_token_service.resolve(db, raw)
        if token is None:
            raise _CREDENTIALS_EXCEPTION
        return Principal(
            organization=token.organization, role=token.role, via_token=True
        )

    # --- User path --------------------------------------------------------
    user = get_current_active_user(get_current_user(credentials, db))

    if x_aegis_org:
        org = _lookup_org(db, x_aegis_org)
        if org is None:
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, detail="Organization not found"
            )
        role = org_service.role_in(db, org, user)
        if role is None:
            # Same response as "no such organization": whether a team exists
            # is not something an outsider gets to learn.
            raise HTTPException(
                status.HTTP_404_NOT_FOUND, detail="Organization not found"
            )
        return Principal(organization=org, role=role, user=user)

    org = org_service.ensure_personal_organization(db, user)
    role = org_service.role_in(db, org, user) or OrgRole.OWNER
    return Principal(organization=org, role=role, user=user)


def require_role(minimum: OrgRole):
    """Dependency factory: the caller must hold at least ``minimum``.

    Reads as the sentence it enforces at the call site:

        principal: Principal = Depends(require_role(OrgRole.ADMIN))
    """

    def _dependency(principal: Principal = Depends(get_principal)) -> Principal:
        if ROLE_RANK[principal.role] < ROLE_RANK[minimum]:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail={
                    "message": (
                        f"This action requires the {minimum.value} role in "
                        f"{principal.organization.name}."
                    ),
                    "reason": "insufficient_role",
                    "required_role": minimum.value,
                },
            )
        return principal

    return _dependency


# Common shorthands. MEMBER is the floor for anything that spends money or
# touches a target; VIEWER can only read.
require_viewer = require_role(OrgRole.VIEWER)
require_member = require_role(OrgRole.MEMBER)
require_admin = require_role(OrgRole.ADMIN)
require_owner = require_role(OrgRole.OWNER)


def billing_user_for(db: Session, principal: Principal) -> User:
    """The user whose subscription entitles the principal's organization."""
    return org_service.billing_user(db, principal.organization)


# --- Gates ----------------------------------------------------------------
def ensure_scan_authorized(user: User) -> None:
    """Raise 403 unless the user has accepted the scan-authorization terms.

    Automated pentesting may only target systems the user is authorized to
    test; acceptance is the attestation. Mirrors the gate detail shape so the
    frontend can branch on ``reason == "scan_terms_required"``.
    """
    if not user.has_accepted_scan_terms:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "You must accept the scan authorization terms before "
                "running scans.",
                "reason": "scan_terms_required",
            },
        )


def ensure_email_verified(user: User) -> None:
    """Raise 403 unless the user has verified their email.

    Mirrors the billing gate's ``{message, reason}`` detail shape so the
    frontend can branch on ``reason == "email_not_verified"``.
    """
    if not user.email_verified:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "message": "Verify your email address before running scans.",
                "reason": "email_not_verified",
            },
        )


def ensure_can_scan(principal: Principal, db: Session) -> None:
    """The full pre-scan gate for whoever is asking.

    A human must have verified their email and accepted the scan terms. An API
    token inherits the attestation from the organization's billing user — CI
    cannot click a checkbox, and the person who issued the token already did.
    """
    user = principal.user or billing_user_for(db, principal)
    if principal.user is not None:
        ensure_email_verified(user)
    ensure_scan_authorized(
        principal.user if principal.user is not None else billing_user_for(db, principal)
    )
