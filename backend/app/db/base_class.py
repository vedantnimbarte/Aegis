"""Declarative base and shared mixins for all ORM models."""
from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import Type

from sqlalchemy import DateTime, Enum as SAEnum, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Root declarative base. All models inherit from this."""


def str_enum(enum_cls: Type[enum.Enum], name: str) -> SAEnum:
    """Build a string-backed Enum column.

    Stored as a VARCHAR holding the enum member's *value* (e.g. ``"free"``),
    not its name (``"FREE"``). Using ``values_callable`` keeps the persisted
    strings aligned with each column's ``server_default`` and the spec, and
    avoids native PG ENUM types (which are painful to ALTER).
    """
    return SAEnum(
        enum_cls,
        name=name,
        native_enum=False,
        values_callable=lambda e: [member.value for member in e],
    )


class UUIDMixin:
    """Adds a UUID primary key generated on the database side."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        server_default=func.gen_random_uuid(),  # requires pgcrypto extension
    )


class TimestampMixin:
    """Adds created_at / updated_at audit columns."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
