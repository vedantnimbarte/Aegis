"""Tests for the grey-box instruction builder (pure, no app deps)."""
from __future__ import annotations

from app.services import greybox_instructions as gi


def test_includes_target_and_credentials() -> None:
    text = gi.build_instruction(
        target_url="https://staging.acme.test",
        login_url="https://staging.acme.test/login",
        username="tester",
        password="s3cret",
        extra="Header: X-Env: staging",
        custom_instructions="Focus on the billing module.",
    )
    assert "https://staging.acme.test" in text
    assert "https://staging.acme.test/login" in text
    assert 'username "tester"' in text
    assert 'password "s3cret"' in text
    assert "X-Env: staging" in text
    assert "Focus on the billing module." in text
    # Always steers Strix toward authenticated-access testing.
    assert "broken access control" in text.lower()


def test_omits_absent_optional_fields() -> None:
    text = gi.build_instruction(target_url="https://app.test")
    assert "https://app.test" in text
    assert "Login page:" not in text
    assert "Credentials:" not in text
    assert "Additional authentication material" not in text
    assert "# Additional instructions" not in text


def test_username_only_without_password() -> None:
    text = gi.build_instruction(target_url="https://app.test", username="tester")
    assert 'username "tester"' in text
    assert "password" not in text.lower()


def test_password_only_without_username() -> None:
    text = gi.build_instruction(target_url="https://app.test", password="pw")
    assert 'password "pw"' in text
    assert "username" not in text.lower()
