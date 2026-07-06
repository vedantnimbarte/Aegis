"""Tests for the pure / security-critical GitHub App helpers.

Network calls aren't exercised (no live GitHub); these cover signature
verification, RS256 App-JWT minting, private-key loading, the check-run
conclusion, and PR comment formatting.
"""
from __future__ import annotations

import base64
import hashlib
import hmac

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from jose import jwt

from app.core.config import settings
from app.services import github_app


@pytest.fixture
def rsa_keypair() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    pub = key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    ).decode()
    return priv, pub


# --- Webhook signatures ---------------------------------------------------
def test_verify_webhook_signature(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "GITHUB_APP_WEBHOOK_SECRET", "s3cret", raising=False)
    payload = b'{"action":"opened"}'
    good = "sha256=" + hmac.new(b"s3cret", payload, hashlib.sha256).hexdigest()
    assert github_app.verify_webhook_signature(payload, good) is True
    assert github_app.verify_webhook_signature(payload, "sha256=deadbeef") is False
    assert github_app.verify_webhook_signature(payload, None) is False
    assert github_app.verify_webhook_signature(b"tampered", good) is False


def test_verify_signature_requires_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "GITHUB_APP_WEBHOOK_SECRET", "", raising=False)
    assert github_app.verify_webhook_signature(b"x", "sha256=abc") is False


# --- App JWT (RS256) ------------------------------------------------------
def test_create_app_jwt(monkeypatch: pytest.MonkeyPatch, rsa_keypair) -> None:
    priv, pub = rsa_keypair
    monkeypatch.setattr(settings, "GITHUB_APP_PRIVATE_KEY", priv, raising=False)
    monkeypatch.setattr(settings, "GITHUB_APP_ID", "12345", raising=False)

    token = github_app.create_app_jwt()
    claims = jwt.decode(token, pub, algorithms=["RS256"])
    assert claims["iss"] == "12345"
    assert claims["exp"] > claims["iat"]


def test_private_key_accepts_base64(monkeypatch: pytest.MonkeyPatch, rsa_keypair) -> None:
    priv, _ = rsa_keypair
    monkeypatch.setattr(
        settings, "GITHUB_APP_PRIVATE_KEY", base64.b64encode(priv.encode()).decode(), raising=False
    )
    assert "-----BEGIN" in github_app._private_key()


def test_private_key_unescapes_newlines(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        settings,
        "GITHUB_APP_PRIVATE_KEY",
        "-----BEGIN KEY-----\\nabc\\n-----END KEY-----",
        raising=False,
    )
    assert "\n" in github_app._private_key()


# --- Check conclusion -----------------------------------------------------
def test_check_conclusion(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "GITHUB_CHECK_FAIL_SEVERITIES", "critical,high", raising=False)
    assert github_app.check_conclusion({"critical": 1}) == "failure"
    assert github_app.check_conclusion({"high": 2}) == "failure"
    assert github_app.check_conclusion({"medium": 5, "low": 1}) == "success"
    assert github_app.check_conclusion({}) == "success"


# --- Comment formatting ---------------------------------------------------
def test_comment_when_clean() -> None:
    body = github_app.format_findings_comment({}, [], total=0)
    assert "No exploitable vulnerabilities" in body


def test_comment_with_findings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "GITHUB_CHECK_FAIL_SEVERITIES", "critical,high", raising=False)
    findings = [
        {"severity": "critical", "title": "SQL injection", "file_path": "app/auth.py:42"},
        {"severity": "low", "title": "Verbose errors", "file_path": None},
    ]
    counts = {"critical": 1, "high": 0, "medium": 0, "low": 1, "info": 0}
    body = github_app.format_findings_comment(
        counts, findings, total=2, report_url="https://dash/scans/abc"
    )
    assert "Aegis Security" in body
    assert "SQL injection" in body
    assert "app/auth.py:42" in body
    assert "Blocking" in body  # a critical finding is present
    assert "https://dash/scans/abc" in body
