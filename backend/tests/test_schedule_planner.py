"""Tests for the recurring-scan cadence math (services/schedule_planner.py)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.services import schedule_planner as sp


def test_daily_advances_one_day() -> None:
    start = datetime(2026, 7, 6, 9, 30, tzinfo=timezone.utc)
    assert sp.compute_next_run(start, "daily") == start + timedelta(days=1)


def test_weekly_advances_seven_days() -> None:
    start = datetime(2026, 7, 6, 9, 30, tzinfo=timezone.utc)
    assert sp.compute_next_run(start, "weekly") == start + timedelta(days=7)


def test_monthly_advances_thirty_days() -> None:
    start = datetime(2026, 7, 6, 9, 30, tzinfo=timezone.utc)
    assert sp.compute_next_run(start, "monthly") == start + timedelta(days=30)


def test_preserves_time_of_day() -> None:
    start = datetime(2026, 7, 6, 14, 45, 12, tzinfo=timezone.utc)
    nxt = sp.compute_next_run(start, "weekly")
    assert (nxt.hour, nxt.minute, nxt.second) == (14, 45, 12)


def test_unknown_frequency_raises() -> None:
    with pytest.raises(ValueError):
        sp.compute_next_run(datetime.now(timezone.utc), "hourly")
