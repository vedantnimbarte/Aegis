"""Attack-surface discovery: parsing and filtering, without the network."""
from __future__ import annotations

from app.services import asm


def test_registrable_domain_strips_scheme_port_and_path() -> None:
    assert asm.registrable_domain("https://app.acme.com:8443/login") == "app.acme.com"
    assert asm.registrable_domain("ACME.COM") == "acme.com"
    assert asm.registrable_domain("acme.com.") == "acme.com"


def test_extract_hosts_takes_names_under_the_domain() -> None:
    entries = [
        {"name_value": "api.acme.com\nwww.acme.com"},
        {"name_value": "acme.com"},
    ]
    assert asm.extract_hosts(entries, "acme.com") == {
        "api.acme.com",
        "www.acme.com",
        "acme.com",
    }


def test_wildcards_are_dropped() -> None:
    """A *.acme.com certificate is not evidence that any particular host exists."""
    assert asm.extract_hosts([{"name_value": "*.acme.com"}], "acme.com") == set()


def test_other_domains_are_excluded() -> None:
    entries = [{"name_value": "api.acme.com\nevil-acme.com\nacme.com.attacker.net"}]
    assert asm.extract_hosts(entries, "acme.com") == {"api.acme.com"}


def test_malformed_entries_are_ignored() -> None:
    assert asm.extract_hosts(["not-a-dict", {}, {"name_value": ""}], "acme.com") == set()


def test_new_hosts_excludes_what_is_already_tracked() -> None:
    discovered = {"api.acme.com", "old.acme.com"}
    known = ["https://old.acme.com/login", "https://unrelated.test"]
    assert asm.new_hosts(discovered, known) == ["api.acme.com"]


def test_new_hosts_is_sorted_for_a_stable_report() -> None:
    assert asm.new_hosts({"c.acme.com", "a.acme.com", "b.acme.com"}, []) == [
        "a.acme.com",
        "b.acme.com",
        "c.acme.com",
    ]


def test_title_extraction() -> None:
    assert asm._extract_title("<html><head><title> Admin Login </title>") == "Admin Login"
    assert asm._extract_title("<html>no title</html>") is None


def test_a_host_that_answered_nothing_is_not_live() -> None:
    assert asm.DiscoveredHost("x.acme.com").is_live is False
    assert asm.DiscoveredHost("x.acme.com", status_code=404).is_live is True
