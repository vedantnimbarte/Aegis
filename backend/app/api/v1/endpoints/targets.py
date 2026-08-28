"""Target endpoints — everything Aegis can be pointed at.

Replaces the old repository endpoints. A repository is one kind of target
here, connected through a source host; a web app, an API, an LLM endpoint or
an MCP server is connected by URL and needs no source at all.
"""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.api.deps import Principal
from app.db.session import get_db
from app.models.enums import GitProvider, OrgRole, TargetKind
from app.schemas.greybox import GreyboxConfigRead, GreyboxConfigUpsert
from app.schemas.target import (
    RepoConnectRequest,
    SourceRepo,
    TargetCreate,
    TargetRead,
    TargetUpdate,
)
from app.services import (
    audit_service,
    billing,
    greybox_service,
    source_hosts,
    target_service,
)

router = APIRouter(prefix="/targets", tags=["targets"])


def _owned(db: Session, target_id: uuid.UUID, principal: Principal):
    target = target_service.get_target(db, target_id, principal.organization)
    if target is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Target not found")
    return target


def _connecting_user(principal: Principal, db: Session):
    """Whose source-host credentials to use when connecting a repository.

    A CI token has none of its own, so it borrows the organization's billing
    user — the person who connected the account in the first place.
    """
    return principal.user or deps.billing_user_for(db, principal)


@router.get("", response_model=list[TargetRead])
def list_targets(
    kind: TargetKind | None = None,
    principal: Principal = Depends(deps.require_viewer),
    db: Session = Depends(get_db),
) -> list[TargetRead]:
    """Every target in the current organization."""
    return [
        TargetRead.from_model(t)
        for t in target_service.list_targets(db, principal.organization, kind)
    ]


@router.get("/available", response_model=list[SourceRepo])
def list_available_repositories(
    provider: GitProvider = GitProvider.GITHUB,
    principal: Principal = Depends(deps.require_member),
    db: Session = Depends(get_db),
) -> list[SourceRepo]:
    """Repositories available on a source host (for the connect dropdown)."""
    user = _connecting_user(principal, db)
    try:
        return [SourceRepo(**repo) for repo in source_hosts.list_repositories(user, provider)]
    except source_hosts.SourceHostError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("", response_model=TargetRead, status_code=status.HTTP_201_CREATED)
def create_target(
    payload: TargetCreate,
    principal: Principal = Depends(deps.require_member),
    db: Session = Depends(get_db),
) -> TargetRead:
    """Add a target by URL (web, API, LLM endpoint, or MCP server).

    Repositories go through ``POST /targets/repos``, which verifies write
    access on the source host first.
    """
    if principal.user is not None:
        deps.ensure_email_verified(principal.user)
    try:
        billing.assert_can_connect_target(db, principal.organization)
    except billing.PaymentRequiredError as exc:
        raise HTTPException(
            status.HTTP_402_PAYMENT_REQUIRED,
            detail={"message": exc.detail, "reason": exc.reason},
        )

    try:
        target = target_service.create_target(
            db,
            org=principal.organization,
            creator=principal.user,
            kind=payload.kind,
            values=payload.model_dump(exclude_none=True),
        )
    except target_service.TargetValidationError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": exc.detail, "fields": exc.fields},
        )

    audit_service.record(
        db,
        organization_id=principal.organization.id,
        action=audit_service.TARGET_CREATED,
        actor=principal.user,
        subject_type="target",
        subject_id=target.id,
        detail={"kind": target.kind.value, "name": target.name},
    )
    return TargetRead.from_model(target)


@router.post("/repos", response_model=TargetRead, status_code=status.HTTP_201_CREATED)
def connect_repository(
    payload: RepoConnectRequest,
    principal: Principal = Depends(deps.require_member),
    db: Session = Depends(get_db),
) -> TargetRead:
    """Connect (or refresh) a source repository for the organization."""
    existing = target_service.get_by_external_repo(
        db, principal.organization, payload.provider, payload.external_repo_id
    )
    user = _connecting_user(principal, db)

    # Only gate *new* connections against the plan's cap; re-syncing an
    # already-connected repo doesn't consume additional capacity.
    if existing is None:
        if principal.user is not None:
            deps.ensure_email_verified(principal.user)
        try:
            billing.assert_can_connect_target(db, principal.organization)
        except billing.PaymentRequiredError as exc:
            raise HTTPException(
                status.HTTP_402_PAYMENT_REQUIRED,
                detail={"message": exc.detail, "reason": exc.reason},
            )

        # The repo id arrives from the client, so ownership is verified here
        # rather than trusting the dropdown: scanning is an active attack and
        # must only ever run against code the caller can actually change.
        try:
            authorized = source_hosts.can_write(
                user, payload.provider, payload.external_repo_id, payload.name
            )
        except source_hosts.SourceHostError as exc:
            raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(exc))
        if not authorized:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                detail=(
                    f"You do not have write access to this repository on "
                    f"{payload.provider.value}. Aegis only scans repositories "
                    "you control."
                ),
            )

    target = target_service.upsert_repo_target(
        db,
        org=principal.organization,
        creator=principal.user,
        provider=payload.provider,
        external_repo_id=payload.external_repo_id,
        name=payload.name,
        clone_url=payload.clone_url,
    )
    if existing is None:
        audit_service.record(
            db,
            organization_id=principal.organization.id,
            action=audit_service.TARGET_CREATED,
            actor=principal.user,
            subject_type="target",
            subject_id=target.id,
            detail={"kind": "repo", "provider": payload.provider.value, "name": target.name},
        )
    return TargetRead.from_model(target)


@router.get("/{target_id}", response_model=TargetRead)
def get_target(
    target_id: uuid.UUID,
    principal: Principal = Depends(deps.require_viewer),
    db: Session = Depends(get_db),
) -> TargetRead:
    return TargetRead.from_model(_owned(db, target_id, principal))


@router.patch("/{target_id}", response_model=TargetRead)
def update_target(
    target_id: uuid.UUID,
    payload: TargetUpdate,
    principal: Principal = Depends(deps.require_member),
    db: Session = Depends(get_db),
) -> TargetRead:
    """Update a target's URL, guardrails, or pull-request gate policy."""
    target = _owned(db, target_id, principal)
    changes = payload.model_dump(exclude_unset=True)
    try:
        target = target_service.update_target(db, target, changes)
    except target_service.TargetValidationError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": exc.detail, "fields": exc.fields},
        )
    audit_service.record(
        db,
        organization_id=principal.organization.id,
        action=audit_service.TARGET_UPDATED,
        actor=principal.user,
        subject_type="target",
        subject_id=target.id,
        detail={"changed": sorted(changes.keys())},
    )
    return TargetRead.from_model(target)


@router.delete("/{target_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_target(
    target_id: uuid.UUID,
    principal: Principal = Depends(deps.require_admin),
    db: Session = Depends(get_db),
):
    """Remove a target and everything recorded about it.

    Admin-only: this destroys scan history and every triage verdict for the
    target, which is not something a member should be able to do by accident.
    """
    target = _owned(db, target_id, principal)
    name = target.name
    target_service.delete_target(db, target)
    audit_service.record(
        db,
        organization_id=principal.organization.id,
        action=audit_service.TARGET_DELETED,
        actor=principal.user,
        subject_type="target",
        subject_id=target_id,
        detail={"name": name},
    )


@router.get("/{target_id}/spec")
def get_derived_spec(
    target_id: uuid.UUID,
    principal: Principal = Depends(deps.require_viewer),
    db: Session = Depends(get_db),
) -> dict:
    """The OpenAPI document derived from this target's source, if any.

    Produced during a scan of a repository target; it is what the agents were
    told to exercise, so it is worth being able to read.
    """
    target = _owned(db, target_id, principal)
    if not target.derived_spec:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            detail=(
                "No API routes have been derived for this target yet. They are "
                "inferred from source during a scan of a repository target."
            ),
        )
    return target.derived_spec


# --- Grey-box (authenticated testing) config -----------------------------
@router.get("/{target_id}/greybox", response_model=GreyboxConfigRead)
def get_greybox(
    target_id: uuid.UUID,
    principal: Principal = Depends(deps.require_member),
    db: Session = Depends(get_db),
) -> GreyboxConfigRead:
    """Return the target's authenticated-testing config (secrets omitted)."""
    target = _owned(db, target_id, principal)
    config = greybox_service.get_config(db, target)
    if config is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="No grey-box config for this target"
        )
    return GreyboxConfigRead.from_model(config)


@router.put("/{target_id}/greybox", response_model=GreyboxConfigRead)
def upsert_greybox(
    target_id: uuid.UUID,
    payload: GreyboxConfigUpsert,
    principal: Principal = Depends(deps.require_member),
    db: Session = Depends(get_db),
) -> GreyboxConfigRead:
    """Create or update the target's authenticated-testing config."""
    target = _owned(db, target_id, principal)
    config = greybox_service.upsert_config(db, target, payload)
    audit_service.record(
        db,
        organization_id=principal.organization.id,
        action=audit_service.GREYBOX_UPDATED,
        actor=principal.user,
        subject_type="target",
        subject_id=target.id,
        # The credentials themselves never reach the audit log.
        detail={"target_url": config.target_url, "has_password": bool(config.password)},
    )
    return GreyboxConfigRead.from_model(config)


@router.delete("/{target_id}/greybox", status_code=status.HTTP_204_NO_CONTENT)
def delete_greybox(
    target_id: uuid.UUID,
    principal: Principal = Depends(deps.require_member),
    db: Session = Depends(get_db),
):
    """Remove the target's authenticated-testing config."""
    target = _owned(db, target_id, principal)
    config = greybox_service.get_config(db, target)
    if config is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No grey-box config")
    greybox_service.delete_config(db, config)
    audit_service.record(
        db,
        organization_id=principal.organization.id,
        action=audit_service.GREYBOX_UPDATED,
        actor=principal.user,
        subject_type="target",
        subject_id=target.id,
        detail={"removed": True},
    )
