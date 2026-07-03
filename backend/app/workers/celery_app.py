"""Celery application instance.

Start a worker with:
    celery -A app.workers.celery_app.celery worker --loglevel=info
"""
from __future__ import annotations

from celery import Celery

from app.core.config import settings

celery = Celery(
    "aegis",
    broker=settings.celery_broker,
    backend=settings.celery_backend,
    include=["app.workers.tasks"],
)

celery.conf.update(
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Strix scans are long-running; give them generous time limits.
    task_soft_time_limit=60 * 60,       # 1h soft
    task_time_limit=60 * 60 + 300,      # 1h5m hard
    worker_prefetch_multiplier=1,       # fair dispatch for long tasks
)
