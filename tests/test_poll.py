"""Phase 9 Batch 1 — poll + free diff + last-seen store (offline only, no LLM, no network).

Key assertions:
- The diff gate short-circuits: no change → changed=False; a real change → changed=True
- First run (no prior hash) is always treated as changed
- poll_all does NOT modify the store (caller commits after successful downstream work)
- HashStore persists correctly across reload
- normalize_html strips nav/script/style boilerplate
"""

from pathlib import Path

import httpx

from patchwork_assurance.config import SourceEntry
from patchwork_assurance.core.agent.poll import (
    PollResult,
    compute_hash,
    normalize_html,
    poll_all,
    poll_source,
)
from patchwork_assurance.core.agent.store import HashStore

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_HTML = b"""
<html>
<head><title>SB 26-189</title></head>
<body>
<nav>Menu navigation ignored</nav>
<header>Site header ignored</header>
<main>
  <h1>SB 26-189 Status</h1>
  <p>Status: Enacted</p>
  <p>Effective: 2026-01-01</p>
  <p>This bill creates requirements for deployers of AI systems.</p>
</main>
<footer>Footer content ignored</footer>
<script>var x = 1;</script>
<style>.btn { color: red; }</style>
</body>
</html>
"""

_HTML_CHANGED = _HTML.replace(b"Enacted", b"Enacted \xe2\x80\x94 amended 2026-06-01")

_SOURCE = SourceEntry(
    jurisdiction="co",
    url="https://leg.colorado.gov/bills/sb26-189",
    kind="html",
)


class _FakeResponse:
    def __init__(self, content: bytes, status_code: int = 200) -> None:
        self.content = content
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPError(f"HTTP {self.status_code}")


class _FakeClient:
    """Minimal fake for httpx.Client — accepts keyword args, returns pre-canned responses."""

    def __init__(self, responses: dict[str, bytes]) -> None:
        self._responses = responses

    def get(self, url: str, **kwargs) -> _FakeResponse:
        if url not in self._responses:
            return _FakeResponse(b"", 404)
        return _FakeResponse(self._responses[url])


# ---------------------------------------------------------------------------
# normalize_html
# ---------------------------------------------------------------------------


def test_normalize_html_strips_script_style_nav_header_footer():
    text = normalize_html(_HTML)
    assert "Menu navigation ignored" not in text
    assert "Site header ignored" not in text
    assert "Footer content ignored" not in text
    assert "var x = 1" not in text
    assert ".btn" not in text


def test_normalize_html_preserves_main_content():
    text = normalize_html(_HTML)
    assert "SB 26-189 Status" in text
    assert "Enacted" in text
    assert "deployers of AI systems" in text


def test_normalize_html_is_deterministic():
    assert normalize_html(_HTML) == normalize_html(_HTML)


# ---------------------------------------------------------------------------
# HashStore
# ---------------------------------------------------------------------------


def test_hash_store_get_missing_returns_none(tmp_path: Path):
    store = HashStore(tmp_path / "hashes.json")
    assert store.get("https://example.com") is None


def test_hash_store_set_and_get(tmp_path: Path):
    store = HashStore(tmp_path / "hashes.json")
    store.set("https://example.com", "abc123")
    assert store.get("https://example.com") == "abc123"


def test_hash_store_persist_and_reload(tmp_path: Path):
    p = tmp_path / "hashes.json"
    s1 = HashStore(p)
    s1.set("https://a.com", "hash1")
    s1.set("https://b.com", "hash2")
    s1.save()

    s2 = HashStore(p)
    assert s2.get("https://a.com") == "hash1"
    assert s2.get("https://b.com") == "hash2"


def test_hash_store_save_creates_parent_dirs(tmp_path: Path):
    p = tmp_path / "deep" / "dir" / "hashes.json"
    store = HashStore(p)
    store.set("https://x.com", "h")
    store.save()
    assert p.exists()


# ---------------------------------------------------------------------------
# poll_source — the diff gate
# ---------------------------------------------------------------------------


def test_poll_source_no_change_returns_false(tmp_path: Path):
    current_hash = compute_hash(_HTML, "html")
    store = HashStore(tmp_path / "hashes.json")
    store.set(_SOURCE.url, current_hash)

    result = poll_source(_SOURCE, store, http_client=_FakeClient({_SOURCE.url: _HTML}))

    assert isinstance(result, PollResult)
    assert result.changed is False
    assert result.new_hash == current_hash


def test_poll_source_changed_content_returns_true(tmp_path: Path):
    old_hash = compute_hash(_HTML, "html")
    store = HashStore(tmp_path / "hashes.json")
    store.set(_SOURCE.url, old_hash)

    result = poll_source(_SOURCE, store, http_client=_FakeClient({_SOURCE.url: _HTML_CHANGED}))

    assert result.changed is True
    assert result.new_hash != old_hash


def test_poll_source_first_run_no_prior_hash_is_changed(tmp_path: Path):
    store = HashStore(tmp_path / "hashes.json")  # empty — no prior hash

    result = poll_source(_SOURCE, store, http_client=_FakeClient({_SOURCE.url: _HTML}))

    assert result.changed is True  # None != any_hash


def test_poll_source_does_not_update_store(tmp_path: Path):
    store = HashStore(tmp_path / "hashes.json")

    poll_source(_SOURCE, store, http_client=_FakeClient({_SOURCE.url: _HTML}))

    assert store.get(_SOURCE.url) is None  # caller commits; poll never writes


def test_poll_source_sends_browser_user_agent(tmp_path: Path):
    # Some official sources 403 a default python user-agent; poll must send a browser UA so
    # the fetch (and the change it detects) actually succeeds.
    captured: dict = {}

    class _CapturingClient:
        def get(self, url: str, **kwargs):
            captured.update(kwargs)
            return _FakeResponse(_HTML)

    poll_source(_SOURCE, HashStore(tmp_path / "h.json"), http_client=_CapturingClient())

    assert "User-Agent" in captured["headers"]
    assert "Mozilla" in captured["headers"]["User-Agent"]


# ---------------------------------------------------------------------------
# poll_all
# ---------------------------------------------------------------------------


def test_poll_all_returns_one_result_per_source(tmp_path: Path):
    co = SourceEntry(jurisdiction="co", url="https://co.example.com", kind="html")
    ct = SourceEntry(jurisdiction="ct", url="https://ct.example.com", kind="html")
    store = HashStore(tmp_path / "hashes.json")
    client = _FakeClient({co.url: _HTML, ct.url: _HTML})

    results = poll_all([co, ct], store, http_client=client)

    assert len(results) == 2


def test_poll_all_mixed_changed_and_unchanged(tmp_path: Path):
    co = SourceEntry(jurisdiction="co", url="https://co.example.com", kind="html")
    ct = SourceEntry(jurisdiction="ct", url="https://ct.example.com", kind="html")

    store = HashStore(tmp_path / "hashes.json")
    # CO is already known (unchanged); CT has no prior hash (changed)
    store.set(co.url, compute_hash(_HTML, "html"))

    client = _FakeClient({co.url: _HTML, ct.url: _HTML})
    results = poll_all([co, ct], store, http_client=client)

    by_j = {r.source.jurisdiction: r for r in results}
    assert by_j["co"].changed is False
    assert by_j["ct"].changed is True


def test_poll_all_does_not_modify_store(tmp_path: Path):
    co = SourceEntry(jurisdiction="co", url="https://co.example.com", kind="html")
    store = HashStore(tmp_path / "hashes.json")
    client = _FakeClient({co.url: _HTML})

    poll_all([co], store, http_client=client)

    assert store.get(co.url) is None  # store untouched
