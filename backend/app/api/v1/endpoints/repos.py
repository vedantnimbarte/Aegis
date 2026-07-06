"""Repository endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api import deps
from app.db.session import get_db
from app.models.user import User
from app.schemas.repository import GitHubRepo, RepositoryRead, RepositorySyncRequest
from app.services import billing
from app.services import github as github_service
from app.services import repo_service

router = APIRouter(prefix="/repos", tags=["repositories"])


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
        try:
            billing.assert_can_connect_repo(db, current_user)
        except billing.PaymentRequiredError as exc:
            raise HTTPException(
                status.HTTP_402_PAYMENT_REQUIRED,
                detail={"message": exc.detail, "reason": exc.reason},
            )

    return repo_service.sync_repository(db, current_user, payload)
