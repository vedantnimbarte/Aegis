"""User model."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.encryption import EncryptedString
from app.db.base_class import Base, TimestampMixin, UUIDMixin, str_enum
from app.models.enums import SubscriptionStatus, SubscriptionTier

if TYPE_CHECKING:  # avoid circular imports at runtime
    from app.models.repository import Repository


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(320), unique=True, index=True, nullable=False
    )
    # Nullable because GitHub-OAuth-only users may not set a password.
    hashed_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    # Email/password sign-ups start unverified; GitHub provides a verified email.
    email_verified: Mapped[bool] = mapped_column(
        default=False, server_default="false", nullable=False
    )

    # OAuth token for the GitHub API — encrypted at rest (AES-256-GCM).
    github_token: Mapped[Optional[str]] = mapped_column(
        EncryptedString(1024), nullable=True
    )
    github_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    subscription_tier: Mapped[SubscriptionTier] = mapped_column(
        str_enum(SubscriptionTier, "subscription_tier"),
        default=SubscriptionTier.FREE,
        server_default=SubscriptionTier.FREE.value,
        nullable=False,
    )
    subscription_status: Mapped[SubscriptionStatus] = mapped_column(
        str_enum(SubscriptionStatus, "subscription_status"),
        default=SubscriptionStatus.NONE,
        server_default=SubscriptionStatus.NONE.value,
        nullable=False,
    )
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(
        String(255), unique=True, nullable=True
    )
    stripe_subscription_id: Mapped[Optional[str]] = mapped_column(
        String(255), unique=True, nullable=True
    )
    # End of the current paid period; the gate treats the sub as lapsed past it.
    subscription_current_period_end: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    # When the user accepted the scan-authorization terms (attesting they own
    # or are permitted to test their targets). NULL until accepted; scanning is
    # gated on it. See SECURITY.md.
    scan_terms_accepted_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # --- Integrations (Pro/Enterprise) ----------------------------------
    # BYOK: user-supplied LLM model id (LiteLLM provider/model form) and API
    # key. The key is encrypted at rest; both fall back to the platform's
    # shared config when unset. Only honoured for tiers where byok is allowed.
    llm_model: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    llm_api_key: Mapped[Optional[str]] = mapped_column(
        EncryptedString(1024), nullable=True
    )
    # Slack incoming-webhook URL for scan-complete notifications. Never returned
    # by the API (only a boolean indicating its presence).
    slack_webhook_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)

    # Relationships -------------------------------------------------------
    repositories: Mapped[List["Repository"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    @property
    def has_active_subscription(self) -> bool:
        """True when the user may run scans.

        Requires a live Stripe subscription (``active``/``trialing``) that has
        not passed its billing period end. ``past_due`` still counts as active
        so a failed renewal has a grace window before Stripe cancels it.
        """
        if self.subscription_status not in (
            SubscriptionStatus.ACTIVE,
            SubscriptionStatus.TRIALING,
            SubscriptionStatus.PAST_DUE,
        ):
            return False
        end = self.subscription_current_period_end
        if end is None:
            return True
        # Compare timezone-aware; DB values are stored with tz.
        return end > datetime.now(timezone.utc)

    @property
    def has_accepted_scan_terms(self) -> bool:
        return self.scan_terms_accepted_at is not None

    @property
    def has_llm_key(self) -> bool:
        """Whether a BYOK LLM key is configured (secret itself never exposed)."""
        return bool(self.llm_api_key)

    @property
    def has_slack(self) -> bool:
        return bool(self.slack_webhook_url)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User id={self.id} email={self.email!r}>"
