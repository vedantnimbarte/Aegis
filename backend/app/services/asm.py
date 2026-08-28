"""Attack-surface discovery: find the hosts nobody remembered to tell you about.

Scheduled re-scans of a list somebody typed in is not attack-surface
monitoring — it is cron. The assets that get breached are the ones missing
from that list: the staging box, the old marketing subdomain, the API gateway
someone stood up for a demo. This module goes looking for them.

Discovery uses certificate transparency rather than brute-forced DNS. Every
public TLS certificate is logged, so CT names the hosts an organization has
actually deployed, without sending a single packet at the customer's
infrastructure — the polite order of operations when the next step is
launching exploits.

Found hosts are then probed once over HTTP to see which are live, because a
CT log is a history of every name ever certified, most of which are gone.

The parsing and filtering are pure functions so the rules can be unit-tested
without the network.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterable, Optional
from urllib.parse import urlparse

import httpx

from app.core.config import settings

logger = logging.getLogger("aegis.asm")


class DiscoveryError(Exception):
    """Raised when a discovery source cannot be reached or read."""


@dataclass(frozen=True)
class DiscoveredHost:
    """One hostname found by discovery, with what the probe saw."""

    hostname: str
    url: Optional[str] = None
    status_code: Optional[int] = None
    title: Optional[str] = None

    @property
    def is_live(self) -> bool:
        return self.status_code is not None


# --- Pure helpers ---------------------------------------------------------
def registrable_domain(value: str) -> str:
    """Reduce a URL or hostname to the bare domain CT should be queried for.

    Deliberately naive about public suffixes: it strips a scheme, a port and a
    path, and leaves the rest alone. Over-broad guesses about ``co.uk``-style
    suffixes would query CT for a domain the customer does not own, and
    enumerating someone else's estate is exactly what the authorization gate
    exists to prevent.
    """
    text = value.strip().lower()
    if "://" in text:
        text = urlparse(text).netloc or text
    text = text.split("/", 1)[0].split("@")[-1]
    return text.split(":", 1)[0].strip(".")


def extract_hosts(entries: Iterable[dict], domain: str) -> set[str]:
    """Hostnames from a crt.sh response that belong under ``domain``.

    A CT entry's ``name_value`` may hold several names separated by newlines,
    and wildcards are common. Wildcards are dropped rather than expanded — a
    ``*.acme.com`` certificate is not evidence that any particular host exists.
    """
    suffix = f".{domain}"
    hosts: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        for raw in str(entry.get("name_value") or "").split("\n"):
            name = raw.strip().lower().strip(".")
            if not name or name.startswith("*"):
                continue
            if name == domain or name.endswith(suffix):
                hosts.add(name)
    return hosts


def new_hosts(discovered: Iterable[str], known: Iterable[str]) -> list[str]:
    """Discovered hosts not already tracked, sorted for a stable report."""
    known_set = {registrable_domain(k) for k in known if k}
    return sorted({h for h in discovered if h and h not in known_set})


# --- Network --------------------------------------------------------------
def fetch_certificate_names(domain: str, *, timeout: Optional[float] = None) -> set[str]:
    """Query certificate transparency for names under ``domain``."""
    url = f"{settings.ASM_CRT_SH_URL.rstrip('/')}/"
    try:
        with httpx.Client(
            timeout=timeout or settings.ASM_HTTP_TIMEOUT_SECONDS,
            follow_redirects=True,
        ) as client:
            resp = client.get(
                url,
                params={"q": f"%.{domain}", "output": "json"},
                headers={"User-Agent": "Aegis-ASM/1.0"},
            )
    except httpx.HTTPError as exc:
        raise DiscoveryError(f"Certificate transparency lookup failed: {exc}") from exc

    if resp.status_code != 200:
        raise DiscoveryError(
            f"Certificate transparency lookup returned HTTP {resp.status_code}"
        )
    try:
        entries = resp.json()
    except ValueError as exc:
        raise DiscoveryError("Certificate transparency returned unreadable JSON") from exc
    if not isinstance(entries, list):
        return set()
    return extract_hosts(entries, domain)


def probe(hostname: str, *, timeout: Optional[float] = None) -> DiscoveredHost:
    """One HEAD-like request per host to see whether anything answers.

    HTTPS first, then HTTP: a host that only answers on port 80 is itself
    worth knowing about. Any failure means "did not respond", not an error —
    most names in a CT log are dead, and that is the normal case.
    """
    limit = timeout or settings.ASM_HTTP_TIMEOUT_SECONDS
    for scheme in ("https", "http"):
        url = f"{scheme}://{hostname}"
        try:
            with httpx.Client(
                timeout=limit, follow_redirects=True, verify=scheme == "https"
            ) as client:
                resp = client.get(url, headers={"User-Agent": "Aegis-ASM/1.0"})
        except httpx.HTTPError:
            continue
        return DiscoveredHost(
            hostname=hostname,
            url=str(resp.url),
            status_code=resp.status_code,
            title=_extract_title(resp.text) if resp.text else None,
        )
    return DiscoveredHost(hostname=hostname)


def _extract_title(html: str) -> Optional[str]:
    """The page title, for telling "login portal" from "default nginx page"."""
    lowered = html.lower()
    start = lowered.find("<title")
    if start == -1:
        return None
    open_end = lowered.find(">", start)
    end = lowered.find("</title>", open_end)
    if open_end == -1 or end == -1:
        return None
    return html[open_end + 1 : end].strip()[:200] or None


def discover(
    domain_or_url: str, *, known_hosts: Iterable[str] = (), limit: Optional[int] = None
) -> list[DiscoveredHost]:
    """Find live hosts under a domain that are not already tracked.

    Bounded by ``ASM_MAX_ASSETS_PER_SWEEP`` so one wildcard DNS zone cannot
    fill the targets table — the cap is applied before probing, since probing
    is the expensive half.
    """
    domain = registrable_domain(domain_or_url)
    if not domain or "." not in domain:
        raise DiscoveryError(f"{domain_or_url!r} is not a domain that can be enumerated")

    candidates = new_hosts(fetch_certificate_names(domain), known_hosts)
    ceiling = limit or settings.ASM_MAX_ASSETS_PER_SWEEP
    if len(candidates) > ceiling:
        logger.info(
            "Discovery for %s found %d candidates; probing the first %d",
            domain, len(candidates), ceiling,
        )
        candidates = candidates[:ceiling]

    return [host for host in (probe(name) for name in candidates) if host.is_live]
