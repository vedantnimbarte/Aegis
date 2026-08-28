"""Model registry.

Importing every model here ensures they are all registered on `Base.metadata`
before Alembic autogenerate or `Base.metadata.create_all()` runs.
"""
from app.db.base_class import Base
from app.models.api_token import ApiToken
from app.models.audit import AuditEvent
from app.models.enums import (
    GitProvider,
    IssueTracker,
    OrgRole,
    RetestOutcome,
    ScanFrequency,
    ScanMode,
    ScanStatus,
    ScanTrigger,
    Severity,
    SubscriptionTier,
    TargetKind,
    TriageStatus,
)
from app.models.greybox import GreyboxConfig
from app.models.installation import Installation
from app.models.organization import Organization, OrgMembership
from app.models.report_share import ReportShare
from app.models.scan import Scan
from app.models.schedule import Schedule
from app.models.target import Target
from app.models.triage import FindingTriage
from app.models.user import User
from app.models.vulnerability import Vulnerability

__all__ = [
    "Base",
    "User",
    "Organization",
    "OrgMembership",
    "AuditEvent",
    "ApiToken",
    "ReportShare",
    "Target",
    "Scan",
    "Schedule",
    "Installation",
    "GreyboxConfig",
    "Vulnerability",
    "FindingTriage",
    "SubscriptionTier",
    "OrgRole",
    "TargetKind",
    "GitProvider",
    "ScanStatus",
    "ScanMode",
    "ScanFrequency",
    "ScanTrigger",
    "Severity",
    "TriageStatus",
    "RetestOutcome",
    "IssueTracker",
]
