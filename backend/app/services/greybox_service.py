"""Greybox (authenticated-testing) config persistence.

Callers pass a repository already resolved for the current user, so these
helpers inherit tenant isolation.
"""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.greybox import GreyboxConfig
from app.models.repository import Repository
from app.schemas.greybox import GreyboxConfigUpsert


def get_config(db: Session, repo: Repository) -> Optional[GreyboxConfig]:
    return db.execute(
        select(GreyboxConfig).where(GreyboxConfig.repository_id == repo.id)
    ).scalar_one_or_none()


def upsert_config(
    db: Session, repo: Repository, payload: GreyboxConfigUpsert
) -> GreyboxConfig:
    config = get_config(db, repo)
    fields = payload.model_fields_set

    if config is None:
        config = GreyboxConfig(
            repository_id=repo.id,
            target_url=payload.target_url,
            login_url=payload.login_url,
            username=payload.username,
            password=payload.password or None,
            extra=payload.extra or None,
        )
        db.add(config)
    else:
        config.target_url = payload.target_url
        config.login_url = payload.login_url
        config.username = payload.username
        # Secrets: only touched when explicitly provided ("" clears them).
        if "password" in fields:
            config.password = payload.password or None
        if "extra" in fields:
            config.extra = payload.extra or None

    db.commit()
    db.refresh(config)
    return config


def delete_config(db: Session, config: GreyboxConfig) -> None:
    db.delete(config)
    db.commit()
