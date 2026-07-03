"""Model registry.

Importing every model here ensures they are all registered on `Base.metadata`
before Alembic autogenerate or `Base.metadata.create_all()` runs.
"""
from app.db.base_class import Base
from app.models.enums import ScanMode, ScanStatus, Severity, SubscriptionTier
from app.models.repository import Repository
from app.models.scan import Scan
from app.models.user import User
from app.models.vulnerability import Vulnerability

__all__ = [
    "Base",
    "User",
    "Repository",
    "Scan",
    "Vulnerability",
    "SubscriptionTier",
    "ScanStatus",
    "ScanMode",
    "Severity",
]
