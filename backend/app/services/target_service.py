"""Target persistence — the replacement for the old repository service.

Every lookup is scoped to an organization, which is where tenant isolation now
lives: a scan, a finding and a triage verdict are reachable only through a
target, and a target is reachable only through an organization the caller is a
member of.
"""
from __future__ import annotations

import uuid
from typing import Optional, Sequence
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import GitProvider, TargetKind
from app.models.organization import Organization
from app.models.target import Target, missing_fields
from app.models.user import User


class TargetValidationError(Exception):
    """The submitted target is not usable for its kind."""

    def __init__(self, detail: str, fields: Optional[list[str]] = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.fields = fields or []


def list_targets(
    db: Session, org: Organization, kind: Optional[TargetKind] = None
) -> Sequence[Target]:
    stmt = select(Target).where(Target.organization_id == org.id)
    if kind is not None:
        stmt = stmt.where(Target.kind == kind)
    return db.execute(stmt.order_by(Target.created_at.desc())).scalars().all()


def get_target(
    db: Session, target_id: uuid.UUID, org: Organization
) -> Optional[Target]:
    """Fetch a target *only* if it belongs to the given organization."""
    return db.execute(
        select(Target).where(
            Target.id == target_id, Target.organization_id == org.id
        )
    ).scalar_one_or_none()


def get_by_external_repo(
    db: Session, org: Organization, provider: GitProvider, external_repo_id: str
) -> Optional[Target]:
    return db.execute(
        select(Target).where(
            Target.organization_id == org.id,
            Target.provider == provider,
            Target.external_repo_id == external_repo_id,
        )
    ).scalar_one_or_none()


def find_repo_by_full_name(
    db: Session, org: Organization, full_name: str
) -> Optional[Target]:
    """A connected repo target by its ``owner/repo`` name (webhook routing)."""
    return db.execute(
        select(Target).where(
            Target.organization_id == org.id,
            Target.kind == TargetKind.REPO,
            Target.name == full_name,
        )
    ).scalar_one_or_none()


def default_name_for(kind: TargetKind, values: dict) -> str:
    """A sensible label when the caller did not supply one.

    For an endpoint that is its hostname — "api.acme.com" reads better in a
    list than the full URL with its path and query string.
    """
    if kind is TargetKind.REPO:
        return (values.get("name") or values.get("external_repo_id") or "repository").strip()
    url = (values.get("url") or "").strip()
    host = urlparse(url).netloc if url else ""
    return (values.get("name") or host or url or kind.value).strip()


def validate(kind: TargetKind, values: dict) -> None:
    """Raise ``TargetValidationError`` unless ``values`` suit ``kind``."""
    absent = missing_fields(kind, values)
    if absent:
        raise TargetValidationError(
            f"A {kind.value} target requires: {', '.join(absent)}.", absent
        )
    if kind is TargetKind.REPO and not (values.get("provider")):
        raise TargetValidationError("A repository target requires a provider.", ["provider"])


def create_target(
    db: Session,
    *,
    org: Organization,
    creator: Optional[User],
    kind: TargetKind,
    values: dict,
) -> Target:
    """Create a target after checking the fields its kind needs."""
    validate(kind, values)
    target = Target(
        organization_id=org.id,
        created_by_user_id=creator.id if creator is not None else None,
        kind=kind,
        name=default_name_for(kind, values)[:512],
        provider=values.get("provider"),
        external_repo_id=values.get("external_repo_id"),
        clone_url=values.get("clone_url"),
        url=values.get("url"),
        openapi_url=values.get("openapi_url"),
        max_budget_usd=values.get("max_budget_usd"),
        gate_fail_severities=values.get("gate_fail_severities"),
        discovered_from_id=values.get("discovered_from_id"),
    )
    if values.get("gate_new_findings_only") is not None:
        target.gate_new_findings_only = bool(values["gate_new_findings_only"])
    if values.get("discovery_enabled") is not None:
        target.discovery_enabled = bool(values["discovery_enabled"])

    db.add(target)
    db.commit()
    db.refresh(target)
    return target


# Fields a PATCH may change. Kind, provider and organization are not among
# them: changing what a target *is* would silently invalidate its scan history
# and every triage verdict keyed to it.
_UPDATABLE = (
    "name",
    "url",
    "clone_url",
    "openapi_url",
    "max_budget_usd",
    "gate_fail_severities",
    "gate_new_findings_only",
    "discovery_enabled",
)


def update_target(db: Session, target: Target, changes: dict) -> Target:
    """Apply the subset of ``changes`` a target is allowed to accept."""
    for field in _UPDATABLE:
        if field in changes:
            setattr(target, field, changes[field])
    # Re-check that the target still satisfies its kind after the edit.
    validate(
        target.kind,
        {
            "clone_url": target.clone_url,
            "url": target.url,
            "provider": target.provider,
        },
    )
    db.commit()
    db.refresh(target)
    return target


def delete_target(db: Session, target: Target) -> None:
    db.delete(target)
    db.commit()


def upsert_repo_target(
    db: Session,
    *,
    org: Organization,
    creator: Optional[User],
    provider: GitProvider,
    external_repo_id: str,
    name: str,
    clone_url: str,
) -> Target:
    """Connect a source repository, or refresh it if already connected."""
    target = get_by_external_repo(db, org, provider, external_repo_id)
    if target is None:
        return create_target(
            db,
            org=org,
            creator=creator,
            kind=TargetKind.REPO,
            values={
                "provider": provider,
                "external_repo_id": external_repo_id,
                "name": name,
                "clone_url": clone_url,
            },
        )
    target.name = name
    target.clone_url = clone_url
    db.commit()
    db.refresh(target)
    return target


def count_targets(db: Session, org: Organization) -> int:
    return len(list_targets(db, org))
