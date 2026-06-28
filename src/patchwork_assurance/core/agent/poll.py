"""Poll + free diff gate (Phase 9 Batch 1).

Five-stage pipeline; this module is stages 1-2 (poll + detect change).
No LLM is constructed or called here — the diff gate is the cost-control keystone:
stages 3-4 (assess + draft) fire only when content actually changed.

Public API:
    normalize_html(content)         - extract visible text, strip nav/script/style
    compute_hash(content, kind)     - stable SHA-256; HTML is normalized first
    poll_source(source, store, ...) - fetch one source, diff vs store, return PollResult
    poll_all(source_set, store, ...)- poll every source, return all PollResults

The store is NOT written by poll_all. The caller updates and saves after a
successful downstream stage (so a crash doesn't silently advance the cursor).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from html.parser import HTMLParser

import httpx

from patchwork_assurance.config import SourceEntry
from patchwork_assurance.core.agent.store import HashStore

_SKIP_TAGS = frozenset({"script", "style", "nav", "header", "footer"})

# Some official sources (e.g. nj.gov) 403 a default httpx/python user-agent. A browser-like
# UA is the bounded fix for that whole class of source; genuinely hostile sites (JS/Cloudflare
# challenges) are left to fall back to the agent's manual-review path, not chased here.
# Shared by both fetch sites (poll here, assess stage) so detection and fetch stay consistent.
REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
}


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: list) -> None:
        if tag in _SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in _SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            stripped = data.strip()
            if stripped:
                self._parts.append(stripped)

    def text(self) -> str:
        return " ".join(self._parts)


def normalize_html(content: bytes) -> str:
    """Extract visible text from HTML, skipping boilerplate tags."""
    parser = _TextExtractor()
    parser.feed(content.decode("utf-8", errors="replace"))
    return parser.text()


def compute_hash(content: bytes, kind: str) -> str:
    """Stable, deterministic hash. HTML is text-normalized first to reduce nav-only false positives."""
    if kind == "html":
        return hashlib.sha256(normalize_html(content).encode()).hexdigest()
    return hashlib.sha256(content).hexdigest()


@dataclass
class PollResult:
    source: SourceEntry
    changed: bool
    new_hash: str


def poll_source(
    source: SourceEntry,
    store: HashStore,
    *,
    http_client: httpx.Client | None = None,
) -> PollResult:
    """Fetch one source, normalize, hash, diff vs last-seen store. Returns PollResult.

    changed=True when the hash differs from the stored value (including first run where
    no stored hash exists). The store is not updated here.
    """
    fetch = http_client.get if http_client else httpx.get
    response = fetch(source.url, follow_redirects=True, timeout=30.0, headers=REQUEST_HEADERS)
    response.raise_for_status()

    new_hash = compute_hash(response.content, source.kind)
    prior_hash = store.get(source.url)
    return PollResult(source=source, changed=(prior_hash != new_hash), new_hash=new_hash)


def poll_all(
    source_set: list[SourceEntry],
    store: HashStore,
    *,
    http_client: httpx.Client | None = None,
) -> list[PollResult]:
    """Poll every source in source_set. Returns one PollResult per source.

    The store is NOT modified. Callers commit new hashes after successful downstream work.
    """
    return [poll_source(s, store, http_client=http_client) for s in source_set]
