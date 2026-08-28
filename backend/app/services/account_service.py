"""Profile changes and account deletion.

Deletion is the reason this module exists. In a single-tenant product it is a
row delete; here a user can be the sole owner of an organization that other
people work in, and deleting them would strand that team with no one who can
manage members or restore billing. So deletion is modelled the way this
product models everything else: state the consequence, show the evidence, and
refuse when the evidence says refuse.

Two outputs:

* a **manifest** — an itemized count of exactly what disappears, so nobody
  clicks through a vague warning and loses six months of scan history;
* **blockers** — conditions that make deletion refuse rather than proceed,
  each with the specific action that clears it.

Counting is deliberately done against the real rows rather than estimated. A
manifest that is only roughly right is worse than none: it teaches people that
the number is decorative.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core import security
from app.models.api_token import ApiToken
from app.models.enums import OrgRole, ScanStatus
from app.models.installation import Installation
from app.models.organization import Organization, OrgMembership
from app.models.report_share import ReportShare
from app.models.scan import Scan
from app.models.target import Target
from app.models.triage import FindingTriage
from app.models.user import User
from app.models.vulnerability import Vulnerability


@dataclass(frozen=True)
class Blocker:
    """Something that must be resolved before the account can be deleted."""

    code: str
    message: str
    # What the user has to do about it, in the words of the interface.
    action: str


@dataclass
class DeletionManifest:
    """Exactly what deleting this account destroys."""

    # Organizations that disappear entirely (the user is their only member).
    organizations_deleted: list[str] = field(default_factory=list)
    # Organizations that survive; the user's seat is simply removed.
    organizations_left: list[str] = field(default_factory=list)
    targets: int = 0
    scans: int = 0
    findings: int = 0
    triage_verdicts: int = 0
    api_tokens: int = 0
    share_links: int = 0
    installations: int = 0
    running_scans: int = 0
    blockers: list[Blocker] = field(default_factory=list)

    @property
    def can_delete(self) -> bool:
        return not self.blockers

    @property
    def destroys_anything(self) -> bool:
        """Whether this is a destructive delete or just a seat being given up."""
        return bool(self.organizations_deleted)


def _owned_alone(db: Session, user: User) -> tuple[list[Organization], list[Organization]]:
    """Split the user's organizations into (deleted with them, survive without).

    An organization is destroyed when the user is its only member. When others
    remain it survives — but if the user is its only *owner*, that is a blocker
    rather than a silent hand-off, because picking a successor is not ours to
    do.
    """
    memberships = (
        db.execute(
            select(OrgMembership).where(OrgMembership.user_id == user.id)
        )
        .scalars()
        .all()
    )

    destroyed: list[Organization] = []
    survives: list[Organization] = []
    for membership in memberships:
        org = membership.organization
        if org is None:  # pragma: no cover - FK makes this unreachable
            continue
        member_count = db.execute(
            select(func.count(OrgMembership.id)).where(
                OrgMembership.organization_id == org.id
            )
        ).scalar_one()
        if member_count <= 1:
            destroyed.append(org)
        else:
            survives.append(org)
    return destroyed, survives


def _stranded_organizations(db: Session, user: User) -> list[Organization]:
    """Shared organizations where this user is the only owner."""
    rows = (
        db.execute(
            select(OrgMembership).where(
                OrgMembership.user_id == user.id,
                OrgMembership.role == OrgRole.OWNER,
            )
        )
        .scalars()
        .all()
    )

    stranded: list[Organization] = []
    for membership in rows:
        org = membership.organization
        if org is None:  # pragma: no cover
            continue
        others = db.execute(
            select(func.count(OrgMembership.id)).where(
                OrgMembership.organization_id == org.id,
                OrgMembership.user_id != user.id,
            )
        ).scalar_one()
        if others == 0:
            continue  # nobody left behind; the org goes with them
        remaining_owners = db.execute(
            select(func.count(OrgMembership.id)).where(
                OrgMembership.organization_id == org.id,
                OrgMembership.role == OrgRole.OWNER,
                OrgMembership.user_id != user.id,
            )
        ).scalar_one()
        if remaining_owners == 0:
            stranded.append(org)
    return stranded


def deletion_manifest(db: Session, user: User) -> DeletionManifest:
    """What deleting ``user`` would destroy, and what stops it."""
    destroyed, survives = _owned_alone(db, user)
    manifest = DeletionManifest(
        organizations_deleted=[o.name for o in destroyed],
        organizations_left=[o.name for o in survives],
    )

    org_ids = [o.id for o in destroyed]
    if org_ids:
        manifest.targets = db.execute(
            select(func.count(Target.id)).where(Target.organization_id.in_(org_ids))
        ).scalar_one()
        manifest.scans = db.execute(
            select(func.count(Scan.id))
            .select_from(Scan)
            .join(Target, Target.id == Scan.target_id)
            .where(Target.organization_id.in_(org_ids))
        ).scalar_one()
        manifest.running_scans = db.execute(
            select(func.count(Scan.id))
            .select_from(Scan)
            .join(Target, Target.id == Scan.target_id)
            .where(
                Target.organization_id.in_(org_ids),
                Scan.status.in_((ScanStatus.PENDING, ScanStatus.RUNNING)),
            )
        ).scalar_one()
        manifest.findings = db.execute(
            select(func.count(Vulnerability.id))
            .select_from(Vulnerability)
            .join(Scan, Scan.id == Vulnerability.scan_id)
            .join(Target, Target.id == Scan.target_id)
            .where(Target.organization_id.in_(org_ids))
        ).scalar_one()
        manifest.triage_verdicts = db.execute(
            select(func.count(FindingTriage.id))
            .select_from(FindingTriage)
            .join(Target, Target.id == FindingTriage.target_id)
            .where(Target.organization_id.in_(org_ids))
        ).scalar_one()
        manifest.api_tokens = db.execute(
            select(func.count(ApiToken.id)).where(
                ApiToken.organization_id.in_(org_ids)
            )
        ).scalar_one()
        manifest.installations = db.execute(
            select(func.count(Installation.id)).where(
                Installation.organization_id.in_(org_ids)
            )
        ).scalar_one()
        manifest.share_links = db.execute(
            select(func.count(ReportShare.id))
            .select_from(ReportShare)
            .join(Scan, Scan.id == ReportShare.scan_id)
            .join(Target, Target.id == Scan.target_id)
            .where(Target.organization_id.in_(org_ids))
        ).scalar_one()

    for org in _stranded_organizations(db, user):
        manifest.blockers.append(
            Blocker(
                code="sole_owner",
                message=f"You are the only owner of {org.name}, and other people work in it.",
                action=f"Make someone else an owner of {org.name}, then delete your account.",
            )
        )

    return manifest


def delete_account(db: Session, user: User) -> None:
    """Delete the user and everything that belongs to them alone.

    Organizations where the user is the only member cascade away with them;
    where others remain, only the membership goes. Callers must check
    ``deletion_manifest`` first — this does not re-check the blockers, so that
    the confirmation the user saw is the deletion they get.
    """
    destroyed, _ = _owned_alone(db, user)
    for org in destroyed:
        db.delete(org)
    db.delete(user)
    db.commit()


class PasswordError(Exception):
    """The current password did not match, or the account has none."""


def change_password(db: Session, user: User, *, current: str, new: str) -> User:
    """Replace the password after verifying the current one.

    A GitHub-only account has no password to verify. Rather than let it set one
    unauthenticated — a session-hijack path into permanent account takeover —
    it is sent through the password-reset flow, which proves control of the
    inbox.
    """
    if not user.hashed_password:
        raise PasswordError(
            "This account signs in with GitHub. Use 'Forgot password' to set a "
            "password by email."
        )
    if not security.verify_password(current, user.hashed_password):
        raise PasswordError("That is not your current password.")

    user.hashed_password = security.get_password_hash(new)
    db.commit()
    db.refresh(user)
    return user


def update_profile(
    db: Session,
    user: User,
    *,
    display_name: Optional[str] = None,
    email: Optional[str] = None,
) -> tuple[User, bool]:
    """Apply profile changes. Returns ``(user, email_changed)``.

    Changing the email un-verifies it: the address has not been proven, and
    scanning is gated on a verified address for a reason. The caller sends a
    fresh verification link.
    """
    email_changed = False

    if display_name is not None:
        user.display_name = display_name.strip()[:120] or None

    if email is not None:
        normalized = email.strip().lower()
        if normalized and normalized != user.email:
            user.email = normalized
            user.email_verified = False
            email_changed = True

    db.commit()
    db.refresh(user)
    return user, email_changed
