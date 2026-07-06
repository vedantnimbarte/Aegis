"""Repository model — a GitHub repo connected by a user."""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.greybox import GreyboxConfig
    from app.models.scan import Scan
    from app.models.schedule import Schedule
    from app.models.user import User


class Repository(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "repositories"
    __table_args__ = (
        # A given GitHub repo is connected at most once per user.
        UniqueConstraint("user_id", "github_repo_id", name="uq_repo_user_github"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    github_repo_id: Mapped[str] = mapped_column(String(64), nullable=False)
    name: Mapped[str] = mapped_column(String(512), nullable=False)  # owner/repo
    url: Mapped[str] = mapped_column(String(1024), nullable=False)

    # Relationships -------------------------------------------------------
    user: Mapped["User"] = relationship(back_populates="repositories")
    scans: Mapped[List["Scan"]] = relationship(
        back_populates="repository",
        cascade="all, delete-orphan",
        order_by="desc(Scan.created_at)",
    )
    schedule: Mapped[Optional["Schedule"]] = relationship(
        back_populates="repository",
        cascade="all, delete-orphan",
        uselist=False,
    )
    greybox: Mapped[Optional["GreyboxConfig"]] = relationship(
        back_populates="repository",
        cascade="all, delete-orphan",
        uselist=False,
    )

    @property
    def has_greybox(self) -> bool:
        """Whether authenticated (grey-box) testing is configured."""
        return self.greybox is not None

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Repository id={self.id} name={self.name!r}>"
