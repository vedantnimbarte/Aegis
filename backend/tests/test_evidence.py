"""Evidence bundles: redaction, truncation, and never inventing proof."""
from __future__ import annotations

from datetime import datetime, timezone

from app.services import evidence


def test_authorization_header_value_is_redacted() -> None:
    text = "GET /admin HTTP/1.1\nHost: app.test\nAuthorization: Bearer sk-secret-123\n"
    cleaned = evidence.redact(text)
    assert "sk-secret-123" not in cleaned
    # The header name survives: knowing the request carried auth is part of
    # understanding the finding.
    assert "Authorization" in cleaned
    assert evidence.REDACTED in cleaned


def test_cookies_are_redacted_in_both_directions() -> None:
    text = "Cookie: session=abc123\nSet-Cookie: session=def456; HttpOnly"
    cleaned = evidence.redact(text)
    assert "abc123" not in cleaned
    assert "def456" not in cleaned


def test_password_fields_in_bodies_are_redacted() -> None:
    for raw in ('{"password": "hunter2"}', "username=x&password=hunter2"):
        cleaned = evidence.redact(raw)
        assert "hunter2" not in cleaned


def test_api_key_headers_are_redacted() -> None:
    assert "k-live-9" not in evidence.redact("X-API-Key: k-live-9")


def test_truncation_keeps_both_ends() -> None:
    text = "START" + ("x" * 50_000) + "END"
    out = evidence.truncate(text, limit=200)
    assert out.startswith("START")
    # The verdict of an HTTP transcript is at the end; head-only truncation
    # would leave proof of nothing.
    assert out.endswith("END")
    assert len(out) <= 200


def test_build_assembles_observation_and_provenance() -> None:
    bundle = evidence.build(
        {"request": "GET /a", "response": "200 OK"},
        engine="Strix",
        model="openai/gpt-4o",
        target_url="https://app.test",
        commit_sha="abc1234",
        observed_at=datetime(2026, 8, 28, tzinfo=timezone.utc),
    )
    assert bundle["request"] == "GET /a"
    assert bundle["engine"] == "Strix"
    assert bundle["commit_sha"] == "abc1234"
    assert bundle["observed_at"].startswith("2026-08-28")


def test_build_redacts_on_the_way_in() -> None:
    bundle = evidence.build({"request": "Authorization: Bearer sk-1\n"})
    assert "sk-1" not in bundle["request"]


def test_provenance_alone_is_not_evidence() -> None:
    """A bundle with no observation would dress up "we ran at 10:04" as proof."""
    assert evidence.build({}, engine="Strix", model="m", commit_sha="abc") is None
    assert evidence.build(None) is None


def test_has_proof_ignores_metadata_only_bundles() -> None:
    assert evidence.has_proof({"engine": "Strix"}) is False
    assert evidence.has_proof({"response": "200 OK"}) is True


def test_summarize_names_what_exists() -> None:
    assert evidence.summarize(None) == "No evidence captured"
    assert "request" in evidence.summarize({"request": "GET /"})
