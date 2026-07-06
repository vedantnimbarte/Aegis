"""Enumerations used across the domain models.

Stored as short strings in PostgreSQL (via SQLAlchemy's native Enum) so they
are human-readable in the DB and easy to filter on.
"""
from __future__ import annotations

import enum


class SubscriptionTier(str, enum.Enum):
    FREE = "free"
    STARTER = "starter"
    PRO = "pro"
    ENTERPRISE = "enterprise"


class SubscriptionStatus(str, enum.Enum):
    """Mirrors the subset of Stripe subscription statuses we act on.

    ``NONE`` is our own value for a user who has never subscribed.
    """

    NONE = "none"
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    INCOMPLETE = "incomplete"


class ScanStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class ScanMode(str, enum.Enum):
    QUICK = "quick"
    STANDARD = "standard"
    DEEP = "deep"


class ScanFrequency(str, enum.Enum):
    """Cadence for a recurring scan schedule."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class ScanTrigger(str, enum.Enum):
    """What initiated a scan."""

    MANUAL = "manual"
    SCHEDULED = "scheduled"
    PULL_REQUEST = "pull_request"


class Severity(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"
