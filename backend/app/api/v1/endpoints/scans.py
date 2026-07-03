"""Scan endpoints."""
from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, status

router = APIRouter(prefix="/scans", tags=["scans"])


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def create_scan() -> dict:
    """Create a `pending` Scan row and enqueue a Celery job that runs Strix.

    TODO(phase-2): validate tenant ownership of the repository, enforce the
    subscription tier's scan quota, then dispatch `run_strix_scan.delay(...)`.
    """
    return {"detail": "Not implemented", "endpoint": "POST /scans"}


@router.get("/{scan_id}", status_code=status.HTTP_200_OK)
async def get_scan(scan_id: UUID) -> dict:
    """Return status and metadata for a single scan.

    TODO(phase-2): enforce that the scan belongs to the current user.
    """
    return {"detail": "Not implemented", "endpoint": f"GET /scans/{scan_id}"}


@router.get("/{scan_id}/report", status_code=status.HTTP_200_OK)
async def get_scan_report(scan_id: UUID) -> dict:
    """Return the detailed vulnerability report (grouped by severity) for a scan.

    TODO(phase-2): join Vulnerabilities, enforce tenant isolation.
    """
    return {"detail": "Not implemented", "endpoint": f"GET /scans/{scan_id}/report"}
