"""Reusable FastAPI dependencies for authentication / current-user resolution."""
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core import security
from app.db.session import get_db
from app.models.user import User
from app.services import user_service

# `Authorization: Bearer <token>` — surfaces an "Authorize" button in /docs.
bearer_scheme = HTTPBearer(auto_error=True)

_CREDENTIALS_EXCEPTION = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Resolve the authenticated user from a bearer *access* token."""
    try:
        payload = security.decode_token(credentials.credentials)
    except JWTError:
        raise _CREDENTIALS_EXCEPTION

    # Reject refresh tokens (or anything not minted as an access token).
    if payload.get("type") != security.ACCESS_TOKEN_TYPE:
        raise _CREDENTIALS_EXCEPTION

    subject = payload.get("sub")
    if not subject:
        raise _CREDENTIALS_EXCEPTION

    user = user_service.get_user_by_id(db, subject)
    if user is None:
        raise _CREDENTIALS_EXCEPTION
    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user),
) -> User:
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Inactive user"
        )
    return current_user
