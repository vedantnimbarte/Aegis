"""Repository endpoints."""
from __future__ import annotations

from fastapi import APIRouter, status

router = APIRouter(prefix="/repos", tags=["repositories"])


@router.get("", status_code=status.HTTP_200_OK)
async def list_repositories() -> dict:
    """List the authenticated user's connected repositories (and/or the
    repositories available via their GitHub token).

    TODO(phase-2): fetch from DB + GitHub API.
    """
    return {"detail": "Not implemented", "endpoint": "GET /repos"}


@router.post("", status_code=status.HTTP_201_CREATED)
async def sync_repository() -> dict:
    """Sync/add a GitHub repository to the user's dashboard.

    TODO(phase-2): validate ownership, persist a Repository row.
    """
    return {"detail": "Not implemented", "endpoint": "POST /repos"}
