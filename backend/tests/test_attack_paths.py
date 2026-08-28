"""Attack chains: composing findings into the outcome none of them reach alone."""
from __future__ import annotations

from types import SimpleNamespace

from app.models.enums import Severity
from app.services import attack_paths


def _f(title, severity=Severity.MEDIUM, path="app/api/users.py", fp=None, cwe=None):
    return SimpleNamespace(
        title=title,
        severity=severity,
        file_path=path,
        owasp_category=cwe,
        fingerprint=fp or title.replace(" ", "-").lower(),
        evidence=None,
    )


def test_capabilities_are_inferred_from_title_and_cwe() -> None:
    assert attack_paths.DISCLOSURE in attack_paths.capabilities_of(
        _f("Verbose error discloses internal host")
    )
    assert attack_paths.ACCESS_CONTROL in attack_paths.capabilities_of(
        _f("IDOR on the invoice endpoint")
    )
    assert attack_paths.INJECTION in attack_paths.capabilities_of(
        _f("Unsafe query", cwe="CWE-89")
    )


def test_disclosure_plus_access_control_chains() -> None:
    chains = attack_paths.build_chains(
        [
            _f("Information disclosure in error response", Severity.LOW),
            _f("IDOR on the invoice endpoint", Severity.MEDIUM),
        ]
    )
    assert len(chains) == 1
    chain = chains[0]
    assert "authorization bypass" in chain.title.lower()
    # Composition is what makes it worse: the chain outranks its worst link.
    assert chain.severity is Severity.HIGH
    assert len(chain.fingerprints) == 2


def test_chain_severity_saturates_at_critical() -> None:
    chains = attack_paths.build_chains(
        [
            _f("Hardcoded API key in source", Severity.CRITICAL),
            _f("Authentication bypass on admin route", Severity.CRITICAL),
        ]
    )
    assert chains and chains[0].severity is Severity.CRITICAL


def test_findings_on_different_assets_do_not_chain() -> None:
    """A false chain inflates severity, and inflation is how a report stops
    being read. Findings must touch the same part of the system."""
    chains = attack_paths.build_chains(
        [
            _f("Information disclosure in error response", path="app/api/users.py"),
            _f("IDOR on the invoice endpoint", path="services/billing/pay.py"),
        ]
    )
    assert chains == []


def test_a_single_finding_never_chains() -> None:
    assert attack_paths.build_chains([_f("IDOR on the invoice endpoint")]) == []


def test_unrecognized_findings_are_ignored() -> None:
    assert attack_paths.build_chains(
        [_f("Something odd happened"), _f("Another odd thing")]
    ) == []


def test_findings_with_no_location_are_skipped() -> None:
    # An unknown asset cannot be matched to another with any confidence.
    chains = attack_paths.build_chains(
        [
            _f("Information disclosure in error response", path=None),
            _f("IDOR on the invoice endpoint", path=None),
        ]
    )
    assert chains == []


def test_urls_collapse_to_host_plus_first_segment() -> None:
    assert attack_paths.asset_of(
        SimpleNamespace(file_path="https://api.test/v1/users?id=1", evidence=None)
    ) == "api.test/v1"


def test_serialize_round_trips() -> None:
    chains = attack_paths.build_chains(
        [
            _f("Information disclosure in error response"),
            _f("IDOR on the invoice endpoint"),
        ]
    )
    raw = attack_paths.serialize(chains)
    back = attack_paths.deserialize(raw)
    assert back[0]["title"] == chains[0].title
    assert back[0]["severity"] == chains[0].severity.value


def test_deserialize_tolerates_junk() -> None:
    assert attack_paths.deserialize(None) == []
    assert attack_paths.deserialize([{"nothing": 1}]) == []
