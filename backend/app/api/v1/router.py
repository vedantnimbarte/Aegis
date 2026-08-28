"""Aggregates all v1 endpoint routers into a single APIRouter."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    billing,
    dashboard,
    github,
    orgs,
    scans,
    schedules,
    shares,
    targets,
    users,
)

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(orgs.router)
api_router.include_router(targets.router)
api_router.include_router(scans.router)
api_router.include_router(dashboard.router)
api_router.include_router(schedules.router)
api_router.include_router(github.router)
api_router.include_router(billing.router)
# Public, token-addressed report links — no authentication by design.
api_router.include_router(shares.router)
