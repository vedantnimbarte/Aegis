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


class OrgRole(str, enum.Enum):
    """A member's authority within an organization.

    Ordered least-to-most privileged by ``RANK`` below; every permission check
    is "at least this role", so adding a tier between two existing ones only
    means inserting a rank.

    ``VIEWER`` exists for the auditor handed a read-only seat: they can read
    reports but cannot spend money or attack anything.
    """

    VIEWER = "viewer"
    MEMBER = "member"
    ADMIN = "admin"
    OWNER = "owner"


# Privilege ordering. Kept beside the enum rather than in a service so there is
# exactly one definition of "outranks".
ROLE_RANK: dict[OrgRole, int] = {
    OrgRole.VIEWER: 0,
    OrgRole.MEMBER: 1,
    OrgRole.ADMIN: 2,
    OrgRole.OWNER: 3,
}


class TargetKind(str, enum.Enum):
    """What sort of thing is under test.

    A repository is one kind of target, not the only kind — black-box buyers
    never hand over source, and an LLM endpoint has no repository at all.
    """

    REPO = "repo"          # a source repository (clone, then test)
    WEB = "web"            # a live web application at a URL
    API = "api"            # an HTTP API, optionally described by a spec
    LLM = "llm"            # an LLM-backed endpoint (OWASP LLM Top 10)
    MCP = "mcp"            # a Model Context Protocol server


class GitProvider(str, enum.Enum):
    """Where a repo-kind target's source lives."""

    GITHUB = "github"
    GITLAB = "gitlab"
    BITBUCKET = "bitbucket"


class ScanStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELED = "canceled"


class TriageStatus(str, enum.Enum):
    """A finding's review state, carried across re-scans by fingerprint.

    ``OPEN`` is the default for anything Strix reports. The other two are set
    by a human and suppress the finding from the "needs attention" counts.
    """

    OPEN = "open"
    FALSE_POSITIVE = "false_positive"
    ACCEPTED_RISK = "accepted_risk"
    FIXED = "fixed"


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
    RETEST = "retest"          # re-run one finding's PoC to prove it is fixed
    DISCOVERY = "discovery"    # auto-dispatched for a newly discovered asset


class Severity(str, enum.Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class RetestOutcome(str, enum.Enum):
    """Result of re-running a finding's proof-of-concept.

    ``INCONCLUSIVE`` is deliberately distinct from ``STILL_VULNERABLE``: a
    retest that could not run tells you nothing, and reporting it as "fixed"
    is how a scanner loses a customer's trust for good.
    """

    FIXED = "fixed"
    STILL_VULNERABLE = "still_vulnerable"
    INCONCLUSIVE = "inconclusive"


class IssueTracker(str, enum.Enum):
    """Where a finding gets filed."""

    GITHUB = "github"
    JIRA = "jira"
    LINEAR = "linear"
