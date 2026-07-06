"""Repository endpoints (incl. per-repo grey-box config)."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.db.session import get_db
from app.models.user import User
from app.schemas.greybox import GreyboxConfigRead, GreyboxConfigUpsert
from app.schemas.repository import GitHubRepo, RepositoryRead, RepositorySyncRequest
from app.services import billing, greybox_service
from app.services import github as github_service
from app.services import repo_service

router = APIRouter(prefix="/repos", tags=["repositories"])


def _owned_repo(db: Session, repo_id: uuid.UUID, user: User):
    repo = repo_service.get_repository(db, repo_id, user)
    if repo is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Repository not found")
    return repo


@router.get("", response_model=list[RepositoryRead])
def list_repositories(
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(get_db),
) -> list[RepositoryRead]:
    """List repositories connected to the user's dashboard."""
    return repo_service.list_connected_repos(db, current_user)


@router.get("/available", response_model=list[GitHubRepo])
def list_available_repositories(
    current_user: User = Depends(deps.get_current_active_user),
) -> list[GitHubRepo]:
    """List repositories available from the user's GitHub account (for the
    connect dropdown). Live call to the GitHub API using the stored token.
    """
    if not current_user.github_token:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail="No GitHub token on file. Reconnect your GitHub account.",
        )
    try:
        return github_service.list_user_repositories(current_user.github_token)
    except github_service.GitHubOAuthError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, detail=str(exc))


@router.post("", response_model=RepositoryRead, status_code=status.HTTP_201_CREATED)
def sync_repository(
    payload: RepositorySyncRequest,
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(get_db),
) -> RepositoryRead:
    """Connect (or update) a GitHub repository on the user's dashboard."""
    # Only gate *new* connections against the plan's repo cap; re-syncing an
    # already-connected repo doesn't consume additional capacity.
    already_connected = repo_service.get_by_github_id(
        db, current_user, payload.github_repo_id
    )
    if already_connected is None:
        deps.ensure_email_verified(current_user)
        try:
            billing.assert_can_connect_repo(db, current_user)
        except billing.PaymentRequiredError as exc:
            raise HTTPException(
                status.HTTP_402_PAYMENT_REQUIRED,
                detail={"message": exc.detail, "reason": exc.reason},
            )

    return repo_service.sync_repository(db, current_user, payload)


# --- Grey-box (authenticated testing) config -----------------------------
@router.get("/{repo_id}/greybox", response_model=GreyboxConfigRead)
def get_greybox(
    repo_id: uuid.UUID,
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(get_db),
) -> GreyboxConfigRead:
    """Return the repo's authenticated-testing config (secrets omitted)."""
    repo = _owned_repo(db, repo_id, current_user)
    config = greybox_service.get_config(db, repo)
    if config is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, detail="No grey-box config for this repository"
        )
    return GreyboxConfigRead.from_model(config)


@router.put("/{repo_id}/greybox", response_model=GreyboxConfigRead)
def upsert_greybox(
    repo_id: uuid.UUID,
    payload: GreyboxConfigUpsert,
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(get_db),
) -> GreyboxConfigRead:
    """Create or update the repo's authenticated-testing config."""
    repo = _owned_repo(db, repo_id, current_user)
    config = greybox_service.upsert_config(db, repo, payload)
    return GreyboxConfigRead.from_model(config)


@router.delete("/{repo_id}/greybox", status_code=status.HTTP_204_NO_CONTENT)
def delete_greybox(
    repo_id: uuid.UUID,
    current_user: User = Depends(deps.get_current_active_user),
    db: Session = Depends(get_db),
) -> None:
    """Remove the repo's authenticated-testing config."""
    repo = _owned_repo(db, repo_id, current_user)
    config = greybox_service.get_config(db, repo)
    if config is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="No grey-box config")
    greybox_service.delete_config(db, config)
