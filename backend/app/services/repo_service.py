"""Repository persistence helpers.

All lookups are scoped to the owning user, enforcing tenant isolation
(spec §5) at the data-access layer rather than relying on endpoints alone.
"""
from __future__ import annotations

import uuid
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.repository import Repository
from app.models.user import User
from app.schemas.repository import RepositorySyncRequest


def list_connected_repos(db: Session, user: User) -> Sequence[Repository]:
    return db.execute(
        select(Repository)
        .where(Repository.user_id == user.id)
        .order_by(Repository.created_at.desc())
    ).scalars().all()


def get_repository(
    db: Session, repository_id: uuid.UUID, user: User
) -> Optional[Repository]:
    """Fetch a repository *only* if it belongs to the given user."""
    return db.execute(
        select(Repository).where(
            Repository.id == repository_id,
            Repository.user_id == user.id,
        )
    ).scalar_one_or_none()


def get_by_github_id(
    db: Session, user: User, github_repo_id: str
) -> Optional[Repository]:
    """Fetch a user's connected repo by its GitHub id, if any."""
    return db.execute(
        select(Repository).where(
            Repository.user_id == user.id,
            Repository.github_repo_id == github_repo_id,
        )
    ).scalar_one_or_none()


def sync_repository(
    db: Session, user: User, payload: RepositorySyncRequest
) -> Repository:
    """Connect a GitHub repo to the dashboard, or update it if already present."""
    repo = db.execute(
        select(Repository).where(
            Repository.user_id == user.id,
            Repository.github_repo_id == payload.github_repo_id,
        )
    ).scalar_one_or_none()

    if repo is None:
        repo = Repository(
            user_id=user.id,
            github_repo_id=payload.github_repo_id,
            name=payload.name,
            url=payload.url,
        )
        db.add(repo)
    else:
        repo.name = payload.name
        repo.url = payload.url

    db.commit()
    db.refresh(repo)
    return repo
