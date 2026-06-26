"""Provenance allowlist (Phase 9 Batch 5).

Guards the agent ingestion path: a draft whose source_url domain is not in the allowlist is
rejected at the gate, before any files are staged. Complements scan_for_injection — injection
catches malicious *content*; provenance catches unvetted *sources*.

The allowlist is configured in Settings.allowed_source_domains (env-overridable data, not code).
Adding a jurisdiction = adding its official domain to the list.

Public API:
    extract_domain   - hostname from a URL string
    is_allowed       - True if url's domain matches or is a subdomain of an allowed domain
    check_provenance - returns a rejection reason string, or None if clean
"""

from __future__ import annotations

from urllib.parse import urlparse


def extract_domain(url: str) -> str:
    """Return the hostname of a URL, lowercased. Returns '' for unparseable or empty URLs."""
    try:
        return urlparse(url).hostname or ""
    except Exception:
        return ""


def is_allowed(url: str, allowed_domains: list[str]) -> bool:
    """True if url's hostname exactly matches or is a subdomain of any entry in allowed_domains."""
    host = extract_domain(url)
    if not host:
        return False
    for domain in allowed_domains:
        d = domain.lower().strip()
        if host == d or host.endswith("." + d):
            return True
    return False


def check_provenance(url: str, allowed_domains: list[str]) -> str | None:
    """Return a rejection reason if url fails the allowlist check, or None if clean.

    An empty or missing url is rejected (integrity rule: every draft must record its source).
    A url whose domain is not in allowed_domains is rejected (provenance: only official sources).
    """
    if not (url or "").strip():
        return "source_url is empty — provenance check failed."
    if not is_allowed(url, allowed_domains):
        host = extract_domain(url)
        return (
            f"source_url domain '{host}' is not in the provenance allowlist. "
            "Only official source domains are accepted."
        )
    return None
