"""Authentication endpoints (GitHub OAuth + JWT issuance/refresh)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError
from sqlalchemy.orm import Session

from app.core import security
from app.db.session import get_db
from app.schemas.auth import GitHubAuthRequest, RefreshRequest
from app.schemas.token import Token
from app.services import github as github_service
from app.services import user_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/github", response_model=Token)
def github_oauth(payload: GitHubAuthRequest, db: Session = Depends(get_db)) -> Token:
    """Exchange a GitHub OAuth code for an access token, upsert the user,
    and return an application JWT pair (access + refresh).
    """
    try:
        gh_token = github_service.exchange_code_for_token(
            payload.code, payload.redirect_uri
        )
        gh_user = github_service.fetch_github_user(gh_token)
    except github_service.GitHubOAuthError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(exc))

    if not gh_user.get("email"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail=(
                "No verified email available from GitHub. Ensure the OAuth app "
                "requests the 'user:email' scope and the account has a verified email."
            ),
        )

    user = user_service.upsert_user_from_github(
        db,
        email=gh_user["email"],
        github_username=gh_user.get("login"),
        github_token=gh_token,
    )

    return Token(
        access_token=security.create_access_token(user.id),
        refresh_token=security.create_refresh_token(user.id),
    )


@router.post("/refresh", response_model=Token)
def refresh_tokens(payload: RefreshRequest, db: Session = Depends(get_db)) -> Token:
    """Exchange a valid refresh token for a new access/refresh pair (rotation)."""
    invalid = HTTPException(
        status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token"
    )
    try:
        claims = security.decode_token(payload.refresh_token)
    except JWTError:
        raise invalid

    if claims.get("type") != security.REFRESH_TOKEN_TYPE:
        raise invalid

    subject = claims.get("sub")
    user = user_service.get_user_by_id(db, subject) if subject else None
    if user is None or not user.is_active:
        raise invalid

    return Token(
        access_token=security.create_access_token(user.id),
        refresh_token=security.create_refresh_token(user.id),
    )
