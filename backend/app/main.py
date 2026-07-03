"""Aegis API — FastAPI application entrypoint.

Run locally with:
    uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import settings
from app.db.session import engine

# Ensure every model is imported so its table is registered on Base.metadata.
import app.models  # noqa: F401  (side-effect import)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup / shutdown hooks.

    We verify DB connectivity on boot so the container fails fast if the
    database is unreachable. Schema creation itself is owned by Alembic
    migrations (`alembic upgrade head`), not by the app process.
    """
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    yield
    engine.dispose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# --- Middleware -----------------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=[str(o) for o in settings.BACKEND_CORS_ORIGINS],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Health check ---------------------------------------------------------
@app.get("/health", tags=["system"])
async def health_check() -> dict:
    return {"status": "ok", "environment": settings.ENVIRONMENT}


# --- API v1 routes --------------------------------------------------------
app.include_router(api_router, prefix=settings.API_V1_PREFIX)
