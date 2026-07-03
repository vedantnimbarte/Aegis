"""User model."""
from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.encryption import EncryptedString
from app.db.base_class import Base, TimestampMixin, UUIDMixin, str_enum
from app.models.enums import SubscriptionTier

if TYPE_CHECKING:  # avoid circular imports at runtime
    from app.models.repository import Repository


class User(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(
        String(320), unique=True, index=True, nullable=False
    )
    # Nullable because GitHub-OAuth-only users may not set a password.
    hashed_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

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
    stripe_customer_id: Mapped[Optional[str]] = mapped_column(
        String(255), unique=True, nullable=True
    )

    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)

    # Relationships -------------------------------------------------------
    repositories: Mapped[List["Repository"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User id={self.id} email={self.email!r}>"
