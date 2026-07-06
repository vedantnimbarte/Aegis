"""Aggregates all v1 endpoint routers into a single APIRouter."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.v1.endpoints import auth, billing, repos, scans, users

api_router = APIRouter()
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(repos.router)
api_router.include_router(scans.router)
api_router.include_router(billing.router)
