"""Write and read the organization audit log.

One rule: recording an event must never break the thing it records. Auditing a
scan launch is worth a row, not worth a 500 — so ``record`` swallows its own
failures and logs them. The trade is deliberate and narrow: this log is for
answering "who changed this", not for anything a control depends on.

Actions are stable dotted strings. They are constants rather than free text so
the log can be filtered, and so renaming one is a change you can grep for.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audit import AuditEvent
from app.models.organization import Organization
from app.models.user import User

logger = logging.getLogger("aegis.audit")

# --- Action vocabulary ----------------------------------------------------
TARGET_CREATED = "target.created"
TARGET_UPDATED = "target.updated"
TARGET_DELETED = "target.deleted"
TARGET_DISCOVERED = "target.discovered"
SCAN_CREATED = "scan.created"
SCAN_CANCELED = "scan.canceled"
RETEST_REQUESTED = "finding.retest_requested"
FINDING_TRIAGED = "finding.triaged"
FINDING_FILED = "finding.filed"
AUTOFIX_OPENED = "autofix.pr_opened"
GREYBOX_UPDATED = "greybox.updated"
MEMBER_ADDED = "member.added"
MEMBER_ROLE_CHANGED = "member.role_changed"
MEMBER_REMOVED = "member.removed"
TOKEN_CREATED = "token.created"
TOKEN_REVOKED = "token.revoked"
SHARE_CREATED = "share.created"
SHARE_REVOKED = "share.revoked"
SHARE_VIEWED = "share.viewed"
INTEGRATION_UPDATED = "integration.updated"
ORG_CREATED = "org.created"


def record(
    db: Session,
    *,
    organization_id: uuid.UUID,
    action: str,
    actor: Optional[User] = None,
    subject_type: Optional[str] = None,
    subject_id: Optional[Any] = None,
    detail: Optional[dict] = None,
) -> Optional[AuditEvent]:
    """Append one event. Returns None if the write failed (never raises).

    The caller's transaction is left alone: this commits only the event, so an
    audited action that later rolls back still leaves the attempt on record.
    """
    try:
        event = AuditEvent(
            organization_id=organization_id,
            actor_user_id=actor.id if actor is not None else None,
            actor_email=actor.email if actor is not None else None,
            action=action,
            subject_type=subject_type,
            subject_id=str(subject_id) if subject_id is not None else None,
            detail=detail,
        )
        db.add(event)
        db.commit()
        return event
    except Exception:  # noqa: BLE001 - the log must never break the action
        logger.exception("Failed to record audit event %s", action)
        db.rollback()
        return None


def list_events(
    db: Session,
    org: Organization,
    *,
    action: Optional[str] = None,
    limit: int = 200,
) -> Sequence[AuditEvent]:
    """This organization's history, newest first."""
    stmt = select(AuditEvent).where(AuditEvent.organization_id == org.id)
    if action:
        stmt = stmt.where(AuditEvent.action == action)
    stmt = stmt.order_by(AuditEvent.created_at.desc()).limit(min(limit, 1000))
    return db.execute(stmt).scalars().all()
