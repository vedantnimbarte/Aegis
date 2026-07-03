"""User endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api import deps
from app.models.user import User
from app.schemas.user import UserRead

router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_model=UserRead)
def read_current_user(current_user: User = Depends(deps.get_current_active_user)) -> User:
    """Return the authenticated user's profile and subscription status."""
    return current_user
