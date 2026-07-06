"""Recurring-scan cadence math — pure, dependency-free.

Kept free of app/model imports so the next-run computation is unit-testable in
isolation. Frequencies are plain strings (the enum's ``value``).
"""
from __future__ import annotations

from datetime import datetime, timedelta

# Interval in days for each cadence. "monthly" is a flat 30 days — good enough
# for attack-surface monitoring and keeps the math dependency-free.
INTERVAL_DAYS: dict[str, int] = {
    "daily": 1,
    "weekly": 7,
    "monthly": 30,
}


def compute_next_run(from_dt: datetime, frequency: str) -> datetime:
    """Return the next run time one interval after ``from_dt``."""
    days = INTERVAL_DAYS.get(frequency)
    if days is None:
        raise ValueError(f"Unknown scan frequency: {frequency!r}")
    return from_dt + timedelta(days=days)
