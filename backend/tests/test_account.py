"""Account deletion rules and password changes.

The manifest counts are DB queries and are exercised against the running
database elsewhere; what is tested here is the part that decides *whether*
deletion may proceed, and the password path — the two places where being
wrong loses someone their data or their account.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core import security
from app.services import account_service


class _StubSession:
    """A session that records nothing and commits nothing."""

    def __init__(self) -> None:
        self.committed = False
        self.deleted: list = []

    def commit(self) -> None:
        self.committed = True

    def refresh(self, _obj) -> None:
        pass

    def delete(self, obj) -> None:
        self.deleted.append(obj)


def _manifest(**kwargs) -> account_service.DeletionManifest:
    return account_service.DeletionManifest(**kwargs)


def test_a_manifest_with_no_blockers_can_delete() -> None:
    assert _manifest().can_delete is True


def test_a_blocker_stops_deletion() -> None:
    manifest = _manifest(
        blockers=[
            account_service.Blocker(
                code="sole_owner", message="m", action="Make someone else an owner."
            )
        ]
    )
    assert manifest.can_delete is False


def test_destroys_anything_distinguishes_leaving_from_deleting() -> None:
    """Giving up a seat in someone else's org is not the same as destroying it,
    and the confirmation copy has to be able to tell the difference."""
    leaving = _manifest(organizations_left=["Acme"])
    assert leaving.destroys_anything is False

    destroying = _manifest(organizations_deleted=["Acme"], targets=3)
    assert destroying.destroys_anything is True


def test_blocker_carries_the_action_that_clears_it() -> None:
    blocker = account_service.Blocker(
        code="sole_owner",
        message="You are the only owner of Acme, and other people work in it.",
        action="Make someone else an owner of Acme, then delete your account.",
    )
    # A blocker that says no without saying how is a dead end.
    assert blocker.action
    assert "owner" in blocker.action


# --- Password changes ------------------------------------------------------
def test_password_change_requires_the_current_one() -> None:
    user = SimpleNamespace(hashed_password=security.get_password_hash("old-password"))
    with pytest.raises(account_service.PasswordError) as exc:
        account_service.change_password(
            _StubSession(), user, current="wrong", new="new-password-1"
        )
    assert "current password" in str(exc.value)


def test_password_change_replaces_the_hash() -> None:
    user = SimpleNamespace(hashed_password=security.get_password_hash("old-password"))
    db = _StubSession()
    account_service.change_password(
        db, user, current="old-password", new="new-password-1"
    )
    assert db.committed
    assert security.verify_password("new-password-1", user.hashed_password)
    assert not security.verify_password("old-password", user.hashed_password)


def test_a_github_only_account_is_sent_through_password_reset() -> None:
    """Letting a session with no password set one is a hijack path straight to
    permanent account takeover; proving control of the inbox is the point."""
    user = SimpleNamespace(hashed_password=None)
    with pytest.raises(account_service.PasswordError) as exc:
        account_service.change_password(
            _StubSession(), user, current="", new="new-password-1"
        )
    assert "Forgot password" in str(exc.value)


# --- Profile ---------------------------------------------------------------
def test_changing_the_email_unverifies_it() -> None:
    user = SimpleNamespace(
        display_name=None, email="old@example.com", email_verified=True
    )
    _, changed = account_service.update_profile(
        _StubSession(), user, email="New@Example.com"
    )
    assert changed is True
    assert user.email == "new@example.com"  # normalized
    assert user.email_verified is False


def test_resubmitting_the_same_email_changes_nothing() -> None:
    user = SimpleNamespace(
        display_name=None, email="same@example.com", email_verified=True
    )
    _, changed = account_service.update_profile(
        _StubSession(), user, email="  SAME@example.com "
    )
    assert changed is False
    # Verification must survive a no-op save, or saving a display name would
    # silently lock the user out of scanning.
    assert user.email_verified is True


def test_display_name_is_trimmed_and_blank_clears_it() -> None:
    user = SimpleNamespace(display_name="Old", email="a@b.c", email_verified=True)
    account_service.update_profile(_StubSession(), user, display_name="  Ada Lovelace  ")
    assert user.display_name == "Ada Lovelace"

    account_service.update_profile(_StubSession(), user, display_name="   ")
    assert user.display_name is None


def test_display_name_is_bounded() -> None:
    user = SimpleNamespace(display_name=None, email="a@b.c", email_verified=True)
    account_service.update_profile(_StubSession(), user, display_name="x" * 500)
    assert len(user.display_name) == 120
