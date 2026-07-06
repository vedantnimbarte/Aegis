"""Greybox model — authenticated (behind-login) testing config for a repo.

Holds a live target URL plus test credentials so Strix can log in and exercise
authenticated functionality. Secret fields (``password``, ``extra``) are
encrypted at rest with AES-256-GCM via ``EncryptedString`` and are never
returned by the API (only booleans indicating their presence).
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.encryption import EncryptedString
from app.db.base_class import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.repository import Repository


class GreyboxConfig(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "greybox_configs"
    __table_args__ = (
        UniqueConstraint("repository_id", name="uq_greybox_repository"),
    )

    repository_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("repositories.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    # Live application under test + optional login page.
    target_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    login_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)

    # Username is not a secret; password and free-form extras are encrypted.
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    password: Mapped[Optional[str]] = mapped_column(EncryptedString(512), nullable=True)
    # Free-form auth material: headers, cookies, tokens, or notes.
    extra: Mapped[Optional[str]] = mapped_column(EncryptedString(4096), nullable=True)

    repository: Mapped["Repository"] = relationship(back_populates="greybox")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<GreyboxConfig repo={self.repository_id} target={self.target_url!r}>"
