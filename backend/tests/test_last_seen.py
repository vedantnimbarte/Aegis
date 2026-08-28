"""The last-seen throttle.

This runs on every authenticated request, so the only thing worth testing is
that it usually does *nothing*: a write per request would cost more than the
figure it feeds is worth.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from app.api import deps


class _StubSession:
    """Counts the writes the throttle decides to make."""

    def __init__(self) -> None:
        self.executed = 0

    def execute(self, _stmt) -> None:
        self.executed += 1

    def commit(self) -> None:
        pass


def _user(last_seen_at):
    return SimpleNamespace(id="00000000-0000-0000-0000-000000000001", last_seen_at=last_seen_at)


def test_a_user_never_seen_before_is_recorded() -> None:
    db, user = _StubSession(), _user(None)
    deps._touch_last_seen(db, user)
    assert db.executed == 1
    assert user.last_seen_at is not None


def test_a_user_seen_a_moment_ago_is_not_written_again() -> None:
    seen = datetime.now(timezone.utc) - timedelta(seconds=30)
    db, user = _StubSession(), _user(seen)
    deps._touch_last_seen(db, user)
    assert db.executed == 0
    assert user.last_seen_at == seen


def test_a_user_seen_beyond_the_interval_is_refreshed() -> None:
    stale = datetime.now(timezone.utc) - deps._LAST_SEEN_INTERVAL - timedelta(seconds=1)
    db, user = _StubSession(), _user(stale)
    deps._touch_last_seen(db, user)
    assert db.executed == 1
    assert user.last_seen_at > stale
