"""Database engine and session management."""
from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

# `pool_pre_ping` recycles dead connections (important behind managed PG /
# PgBouncer). Convert the pydantic DSN to a plain string for SQLAlchemy.
#
# `hide_parameters` is on unconditionally — including in DEBUG. Without it,
# SQLAlchemy appends the bound parameters to every StatementError and echoes
# them in query logs, so one failed INSERT prints a user's decrypted
# `github_token` (and LLM key, and Slack webhook) in plaintext, defeating the
# at-rest encryption those columns exist to provide. The cost is that
# debugging a DB error no longer shows the offending values; re-enable it
# locally and temporarily if you need them, never on a box with real tokens.
engine = create_engine(
    str(settings.DATABASE_URL),
    pool_pre_ping=True,
    echo=settings.DEBUG,
    hide_parameters=True,
    future=True,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    class_=Session,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a request-scoped DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
