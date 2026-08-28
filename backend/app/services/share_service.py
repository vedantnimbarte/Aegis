"""Expiring public links to a single report.

The buyer is the founder mid-sales-cycle: their prospect's security reviewer
wants the pentest report, and provisioning them a dashboard account is not
going to happen. A share link hands over exactly one report, read-only, until
it expires.

Every link expires — there is no "never" option — because a permanent URL to a
document describing how to attack the customer is a leak with a long fuse.
Only the token's digest is stored, for the same reason it is for API tokens.
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.report_share import ReportShare
from app.models.scan import Scan
from app.models.user import User

_TOKEN_BYTES = 32


def hash_token(plaintext: str) -> str:
    return hashlib.sha256(plaintext.encode("utf-8")).hexdigest()


def share_url(token: str) -> str:
    return f"{settings.DASHBOARD_URL}/shared/{token}"


def _ttl_days(requested: Optional[int]) -> int:
    """Clamp the requested lifetime to the configured maximum."""
    if not requested:
        return settings.REPORT_SHARE_DEFAULT_TTL_DAYS
    return max(1, min(requested, settings.REPORT_SHARE_MAX_TTL_DAYS))


def create_share(
    db: Session,
    *,
    scan: Scan,
    creator: Optional[User],
    label: Optional[str] = None,
    expires_in_days: Optional[int] = None,
    include_poc: bool = False,
) -> tuple[ReportShare, str]:
    """Mint a link. Returns ``(row, plaintext_token)`` — the token is final."""
    plaintext = secrets.token_urlsafe(_TOKEN_BYTES)
    share = ReportShare(
        scan_id=scan.id,
        created_by_user_id=creator.id if creator is not None else None,
        token_hash=hash_token(plaintext),
        label=(label or None),
        expires_at=datetime.now(timezone.utc)
        + timedelta(days=_ttl_days(expires_in_days)),
        include_poc=include_poc,
    )
    db.add(share)
    db.commit()
    db.refresh(share)
    return share, plaintext


def resolve(db: Session, plaintext: str) -> Optional[ReportShare]:
    """The valid share matching ``plaintext``, or None if expired or revoked."""
    share = db.execute(
        select(ReportShare).where(ReportShare.token_hash == hash_token(plaintext))
    ).scalar_one_or_none()
    if share is None or not share.is_valid(datetime.now(timezone.utc)):
        return None
    return share


def record_view(db: Session, share: ReportShare) -> None:
    """Count a view. Best-effort — analytics must not break the page."""
    try:
        share.view_count += 1
        share.last_viewed_at = datetime.now(timezone.utc)
        db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()


def list_shares(db: Session, scan: Scan) -> Sequence[ReportShare]:
    return (
        db.execute(
            select(ReportShare)
            .where(ReportShare.scan_id == scan.id, ReportShare.revoked_at.is_(None))
            .order_by(ReportShare.created_at.desc())
        )
        .scalars()
        .all()
    )


def get_share(
    db: Session, scan: Scan, share_id: uuid.UUID
) -> Optional[ReportShare]:
    return db.execute(
        select(ReportShare).where(
            ReportShare.id == share_id, ReportShare.scan_id == scan.id
        )
    ).scalar_one_or_none()


def revoke(db: Session, share: ReportShare) -> ReportShare:
    """Kill a link immediately. Kept as a row so the audit log still resolves it."""
    if share.revoked_at is None:
        share.revoked_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(share)
    return share
