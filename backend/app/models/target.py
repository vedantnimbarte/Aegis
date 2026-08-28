"""Target — anything Aegis can be pointed at.

This replaces the old ``Repository`` model. A repository is now one *kind* of
target (``TargetKind.REPO``) alongside a live web app, an API, an LLM endpoint
and an MCP server. The distinction matters because half the buyers in this
market never hand over source code, and because an LLM endpoint has no
repository to clone at all.

Field applicability by kind:

    repo   provider + external_repo_id + clone_url (+ optional live url)
    web    url
    api    url (+ optional openapi_url / derived spec)
    llm    url (the chat/completions endpoint under test)
    mcp    url (the MCP server endpoint)

Rather than five sparse tables, one table carries the union and
``validate_for_kind`` states which columns each kind actually requires — the
constraint lives in code because it is a product rule, not a storage rule.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base, TimestampMixin, UUIDMixin, str_enum
from app.models.enums import GitProvider, TargetKind

if TYPE_CHECKING:
    from app.models.greybox import GreyboxConfig
    from app.models.organization import Organization
    from app.models.scan import Scan
    from app.models.schedule import Schedule
    from app.models.user import User


class Target(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "targets"
    __table_args__ = (
        # A given remote repo is connected at most once per organization.
        UniqueConstraint(
            "organization_id", "external_repo_id", name="uq_target_org_external_repo"
        ),
    )

    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    # Who connected it. Kept for the audit trail; authority comes from the org.
    created_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    kind: Mapped[TargetKind] = mapped_column(
        str_enum(TargetKind, "target_kind"),
        default=TargetKind.REPO,
        server_default=TargetKind.REPO.value,
        index=True,
        nullable=False,
    )
    # "owner/repo" for repos, a hostname or free label for everything else.
    name: Mapped[str] = mapped_column(String(512), nullable=False)

    # --- Source-repository fields (kind == repo) -------------------------
    provider: Mapped[Optional[GitProvider]] = mapped_column(
        str_enum(GitProvider, "git_provider"), nullable=True
    )
    # The provider's own id for the repo (GitHub repo id, GitLab project id…).
    external_repo_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    clone_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)

    # --- Live-endpoint fields (kind in web/api/llm/mcp, optional for repo) -
    url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    # Where an OpenAPI document can be fetched, if the team publishes one.
    openapi_url: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    # The most recent spec we derived from source (see services/api_spec.py),
    # kept so the UI can show what will actually be exercised.
    derived_spec: Mapped[Optional[dict]] = mapped_column(JSONB, nullable=True)

    # --- Per-target guardrails and policy --------------------------------
    # Overrides the platform-wide per-scan LLM budget. None = use the default.
    max_budget_usd: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # Comma-separated severities that fail a pull-request check for this
    # target. NULL falls back to the platform default.
    gate_fail_severities: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    # When true (the default), a PR check only fails on findings that are new
    # relative to the previous scan — pre-existing debt is reported, never
    # blocking. A gate that fails on the backlog gets switched off in week two.
    gate_new_findings_only: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default="true", nullable=False
    )

    # --- Attack-surface discovery ----------------------------------------
    # The target this one was discovered from (ASM), if it wasn't added by hand.
    discovered_from_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("targets.id", ondelete="SET NULL"),
        nullable=True,
    )
    # Run subdomain/asset discovery against this target on the beat schedule.
    discovery_enabled: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false", nullable=False
    )

    # Relationships -------------------------------------------------------
    organization: Mapped["Organization"] = relationship(back_populates="targets")
    created_by: Mapped[Optional["User"]] = relationship(
        foreign_keys=[created_by_user_id]
    )
    scans: Mapped[List["Scan"]] = relationship(
        back_populates="target",
        cascade="all, delete-orphan",
        order_by="desc(Scan.created_at)",
    )
    schedule: Mapped[Optional["Schedule"]] = relationship(
        back_populates="target", cascade="all, delete-orphan", uselist=False
    )
    greybox: Mapped[Optional["GreyboxConfig"]] = relationship(
        back_populates="target", cascade="all, delete-orphan", uselist=False
    )

    # --- Derived -----------------------------------------------------------
    @property
    def has_greybox(self) -> bool:
        """Whether authenticated (grey-box) testing is configured."""
        return self.greybox is not None

    @property
    def is_repo(self) -> bool:
        return self.kind is TargetKind.REPO

    @property
    def needs_checkout(self) -> bool:
        """Whether running a scan means cloning source first."""
        return self.kind is TargetKind.REPO and bool(self.clone_url)

    @property
    def live_url(self) -> Optional[str]:
        """The URL to attack, if this target has one.

        A repo may carry one too (a repo target whose app is also deployed),
        in which case the scan tests code and running app together.
        """
        if self.url:
            return self.url
        greybox = self.greybox
        return greybox.target_url if greybox is not None else None

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Target id={self.id} kind={self.kind.value} name={self.name!r}>"


# Which columns each kind cannot do without. Enforced at the service layer so
# the message reaches the user as a 422 instead of an IntegrityError.
REQUIRED_FIELDS: dict[TargetKind, tuple[str, ...]] = {
    TargetKind.REPO: ("clone_url",),
    TargetKind.WEB: ("url",),
    TargetKind.API: ("url",),
    TargetKind.LLM: ("url",),
    TargetKind.MCP: ("url",),
}


def missing_fields(kind: TargetKind, values: dict) -> list[str]:
    """Names of the required fields ``values`` does not supply for ``kind``."""
    return [
        field
        for field in REQUIRED_FIELDS.get(kind, ())
        if not (values.get(field) or "").strip()
    ]
