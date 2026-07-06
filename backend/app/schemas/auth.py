"""Authentication request schemas."""
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """Email/password sign-up payload."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    """Email/password sign-in payload."""

    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class VerifyEmailRequest(BaseModel):
    """Confirm an email address using the emailed token."""

    token: str = Field(..., min_length=1)


class ForgotPasswordRequest(BaseModel):
    """Request a password-reset email."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Complete a password reset with the emailed token."""

    token: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)


class GitHubAuthRequest(BaseModel):
    """Payload the frontend POSTs after the GitHub OAuth redirect returns a code."""

    code: str = Field(..., min_length=1, description="GitHub OAuth authorization code")
    # Optional overrides; fall back to server-configured values when omitted.
    redirect_uri: str | None = None
    # CSRF `state` echoed back by GitHub. The frontend is responsible for
    # verifying it against what it generated before the redirect.
    state: str | None = None


class RefreshRequest(BaseModel):
    refresh_token: str = Field(..., min_length=1)
