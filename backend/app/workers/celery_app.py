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

# Derive Celery's time limits from the scan budget so they always sit *above*
# the worst-case subprocess time (git clone + Strix). This guarantees the task
# hits our own clean TimeoutExpired -> mark-failed path before Celery hard-kills
# the worker mid-scan. Soft adds a 2m buffer; hard adds a further 5m for cleanup.
_scan_budget = settings.GIT_CLONE_TIMEOUT_SECONDS + settings.STRIX_SCAN_TIMEOUT_SECONDS
_soft_time_limit = _scan_budget + 120
_hard_time_limit = _soft_time_limit + 300

# How often Celery Beat checks for due recurring scans (see workers/tasks.py).
_SCHEDULER_TICK_SECONDS = 300.0

celery.conf.update(
    task_track_started=True,
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    # Strix scans are long-running; limits track the configured scan budget.
    task_soft_time_limit=_soft_time_limit,
    task_time_limit=_hard_time_limit,
    worker_prefetch_multiplier=1,       # fair dispatch for long tasks
    # Emit task-lifecycle events so the Prometheus celery-exporter can track
    # scan throughput/failures (the worker must also run with `-E`).
    worker_send_task_events=True,
    task_send_sent_event=True,
    # Beat: poll the DB for due schedules and dispatch them.
    beat_schedule={
        "dispatch-due-scheduled-scans": {
            "task": "app.workers.tasks.enqueue_due_scheduled_scans",
            "schedule": _SCHEDULER_TICK_SECONDS,
        },
    },
)
