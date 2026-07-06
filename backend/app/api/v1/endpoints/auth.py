"""Authentication endpoints (GitHub OAuth + JWT issuance/refresh)."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from jose import JWTError
from sqlalchemy.orm import Session

from app.api import deps
from app.core import security
from app.core.config import settings
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    ForgotPasswordRequest,
    GitHubAuthRequest,
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    ResetPasswordRequest,
    VerifyEmailRequest,
)
from app.schemas.token import Token
from app.services import email as email_service
from app.services import github as github_service
from app.services import user_service

router = APIRouter(prefix="/auth", tags=["auth"])


def _issue_tokens(user_id) -> Token:
    return Token(
        access_token=security.create_access_token(user_id),
        refresh_token=security.create_refresh_token(user_id),
    )


def _dispatch_verification_email(background_tasks: BackgroundTasks, user: User) -> None:
    token = security.create_email_verification_token(user.id)
    verify_url = f"{settings.DASHBOARD_URL}/verify-email?token={token}"
    background_tasks.add_task(
        email_service.send_verification_email, user.email, verify_url
    )


@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> Token:
    """Create an account, email a verification link, and return a JWT pair.

    Sign-in works immediately, but scanning stays gated until the email is
    verified (see the scans endpoint).
    """
    try:
        user = user_service.create_user_with_password(
            db, email=payload.email, password=payload.password
        )
    except user_service.EmailAlreadyExistsError:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )
    _dispatch_verification_email(background_tasks, user)
    return _issue_tokens(user.id)


@router.post("/verify-email")
def verify_email(payload: VerifyEmailRequest, db: Session = Depends(get_db)) -> dict:
    """Confirm an email address with the emailed token (idempotent)."""
    invalid = HTTPException(
        status.HTTP_400_BAD_REQUEST,
        detail="This verification link is invalid or has expired.",
    )
    try:
        claims = security.decode_token(payload.token)
    except JWTError:
        raise invalid
    if claims.get("type") != security.EMAIL_VERIFY_TOKEN_TYPE:
        raise invalid

    subject = claims.get("sub")
    user = user_service.get_user_by_id(db, subject) if subject else None
    if user is None or not user.is_active:
        raise invalid

    user_service.mark_email_verified(db, user)
    return {"detail": "Your email has been verified."}


@router.post("/resend-verification", status_code=status.HTTP_202_ACCEPTED)
def resend_verification(
    background_tasks: BackgroundTasks,
    current_user: User = Depends(deps.get_current_active_user),
) -> dict:
    """Re-send the verification email to the signed-in user (no-op if verified)."""
    if not current_user.email_verified:
        _dispatch_verification_email(background_tasks, current_user)
    return {"detail": "If your email is unverified, a new link has been sent."}


@router.post("/login", response_model=Token)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> Token:
    """Authenticate with email + password and return a JWT pair."""
    user = user_service.authenticate_user(
        db, email=payload.email, password=payload.password
    )
    if user is None or not user.is_active:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )
    return _issue_tokens(user.id)


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

    return _issue_tokens(user.id)


@router.post("/forgot-password", status_code=status.HTTP_202_ACCEPTED)
def forgot_password(
    payload: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> dict:
    """Email a password-reset link. Always returns the same response so it
    cannot be used to probe which emails have accounts (anti-enumeration).
    """
    user = user_service.get_user_by_email(db, payload.email.strip().lower())
    if user is not None and user.is_active:
        token = security.create_password_reset_token(user.id, user.hashed_password)
        reset_url = f"{settings.DASHBOARD_URL}/reset-password?token={token}"
        # Send off the request thread so SMTP latency never blocks the response.
        background_tasks.add_task(
            email_service.send_password_reset_email, user.email, reset_url
        )
    return {
        "detail": "If an account exists for that email, a password reset link "
        "has been sent."
    }


@router.post("/reset-password", response_model=Token)
def reset_password(
    payload: ResetPasswordRequest, db: Session = Depends(get_db)
) -> Token:
    """Set a new password using a valid reset token, then sign the user in."""
    invalid = HTTPException(
        status.HTTP_400_BAD_REQUEST,
        detail="This password reset link is invalid or has expired.",
    )
    try:
        claims = security.decode_token(payload.token)
    except JWTError:
        raise invalid

    if claims.get("type") != security.PASSWORD_RESET_TOKEN_TYPE:
        raise invalid

    subject = claims.get("sub")
    user = user_service.get_user_by_id(db, subject) if subject else None
    if user is None or not user.is_active:
        raise invalid

    # The token is bound to the password at issue time; a mismatch means it was
    # already used or the password has since changed.
    if claims.get("pwf") != security.password_fingerprint(user.hashed_password):
        raise invalid

    user_service.set_password(db, user, payload.new_password)
    return _issue_tokens(user.id)


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

    return _issue_tokens(user.id)
