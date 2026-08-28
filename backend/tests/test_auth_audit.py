"""Sign-in events in the audit log.

The two things worth pinning: a rejected attempt is still recorded against the
address that was tried (that is what makes a takeover attempt visible), and
the caller address is read from the proxy header when there is one.
"""
from __future__ import annotations

from types import SimpleNamespace

from app.api.v1.endpoints import auth
from app.services import audit_service


class _StubSession:
    """Keeps what was written instead of writing it."""

    def __init__(self) -> None:
        self.added: list = []

    def add(self, obj) -> None:
        self.added.append(obj)

    def commit(self) -> None:
        pass

    def rollback(self) -> None:
        pass


def _request(headers=None, host="10.0.0.9"):
    return SimpleNamespace(
        headers=headers or {}, client=SimpleNamespace(host=host)
    )


def test_a_failed_login_is_recorded_against_the_attempted_address() -> None:
    db = _StubSession()
    auth._record_auth(
        db,
        _request(),
        audit_service.AUTH_LOGIN_FAILED,
        email="nobody@example.com",
        reason="bad_credentials",
    )
    event = db.added[0]
    assert event.action == "auth.login_failed"
    assert event.actor_email == "nobody@example.com"
    assert event.actor_user_id is None
    assert event.detail["reason"] == "bad_credentials"


def test_a_sign_in_event_belongs_to_no_organization() -> None:
    db = _StubSession()
    user = SimpleNamespace(id="u-1", email="someone@example.com")
    auth._record_auth(db, _request(), audit_service.AUTH_LOGIN, user=user, method="password")
    event = db.added[0]
    assert event.organization_id is None
    assert event.actor_email == "someone@example.com"
    assert event.detail == {"ip": "10.0.0.9", "method": "password"}


def test_the_proxy_header_wins_over_the_socket_address() -> None:
    request = _request(headers={"x-forwarded-for": "203.0.113.7, 10.0.0.1"})
    assert auth._client_ip(request) == "203.0.113.7"


def test_the_socket_address_is_used_when_there_is_no_proxy() -> None:
    assert auth._client_ip(_request()) == "10.0.0.9"
