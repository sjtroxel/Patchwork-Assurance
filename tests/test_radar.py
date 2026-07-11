"""Phase 13 Session 1 — LegiScan radar detection (offline only, no LLM, no network).

Key assertions:
- run_radar classifies NEW / CHANGED / unchanged by dedup vs the store on (bill_id, change_hash)
- CHANGED carries the prior issue_number so the caller can comment on the existing issue
- the status floor rejects introduced bills; the relevance floor rejects weak matches
- getBill status enrichment runs only on relevance-survivors (budget guard)
- a bill matching several queries is de-duplicated within a run (highest relevance wins)
- LegiScanClient.get_search paginates and raises on a non-OK payload
- RadarStore persists its rich per-bill value across reload; run_radar never writes it
"""

from pathlib import Path

import httpx
import pytest

from patchwork_assurance.core.agent.radar import (
    LegiScanClient,
    RadarCandidate,
    RadarStore,
    _candidate_summary,
    run_radar,
)

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


def _search_result(bill_id: int, *, relevance: int = 100, change_hash: str = "h", number: str = ""):
    return {
        "bill_id": bill_id,
        "bill_number": number or f"SB{bill_id}",
        "state": "CA",
        "title": f"An act {bill_id}",
        "change_hash": change_hash,
        "relevance": relevance,
        "url": f"https://legiscan.com/CA/bill/{bill_id}",
    }


class _FakeClient:
    """Duck-typed stand-in for LegiScanClient used to drive run_radar.

    search_results: maps a query -> list of raw getSearch dicts.
    statuses:       maps bill_id -> LegiScan status enum (returned by get_bill_status).
    """

    def __init__(self, search_results: dict[str, list[dict]], statuses: dict[int, int]) -> None:
        self._search_results = search_results
        self._statuses = statuses
        self.status_calls: list[int] = []

    def get_search(self, query, *, year=None, max_pages=5):
        return list(self._search_results.get(query, []))

    def get_bill_status(self, bill_id):
        self.status_calls.append(bill_id)
        return self._statuses.get(bill_id)


class _FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict:
        return self._payload

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise httpx.HTTPError(f"HTTP {self.status_code}")


class _FakeHttp:
    """Fake httpx client for LegiScanClient plumbing; dispatches on op + page params."""

    def __init__(self, pages: dict[int, dict] | None = None, bill: dict | None = None) -> None:
        self._pages = pages or {}
        self._bill = bill or {}
        self.captured: list[dict] = []

    def get(self, url, **kwargs):
        params = kwargs["params"]
        self.captured.append(params)
        if params["op"] == "getSearch":
            return _FakeResponse(self._pages[params["page"]])
        if params["op"] == "getBill":
            return _FakeResponse({"status": "OK", "bill": self._bill})
        raise AssertionError(f"unexpected op {params['op']!r}")


# ---------------------------------------------------------------------------
# run_radar — classification
# ---------------------------------------------------------------------------


def test_run_radar_new_candidate(tmp_path: Path):
    client = _FakeClient({"artificial intelligence": [_search_result(1)]}, statuses={1: 4})
    store = RadarStore(tmp_path / "radar.json")  # empty

    run = run_radar(client, store, queries=("artificial intelligence",))

    assert len(run.new) == 1
    assert run.new[0].kind == "NEW"
    assert run.new[0].bill_id == 1
    assert run.changed == []


def test_run_radar_changed_hash_carries_issue_number(tmp_path: Path):
    client = _FakeClient({"q": [_search_result(1, change_hash="new-hash")]}, statuses={1: 4})
    store = RadarStore(tmp_path / "radar.json")
    store.set(1, change_hash="old-hash", first_seen="2026-07-01", issue_number=42)

    run = run_radar(client, store, queries=("q",))

    assert run.new == []
    assert len(run.changed) == 1
    assert run.changed[0].kind == "CHANGED"
    assert run.changed[0].issue_number == 42  # so the caller can comment on the existing issue


def test_run_radar_unchanged_hash_is_noop(tmp_path: Path):
    client = _FakeClient({"q": [_search_result(1, change_hash="same")]}, statuses={1: 4})
    store = RadarStore(tmp_path / "radar.json")
    store.set(1, change_hash="same", first_seen="2026-07-01", issue_number=42)

    run = run_radar(client, store, queries=("q",))

    assert run.new == []
    assert run.changed == []
    assert run.unchanged == 1


# ---------------------------------------------------------------------------
# run_radar — filters
# ---------------------------------------------------------------------------


def test_status_floor_rejects_introduced(tmp_path: Path):
    # bill 1 is introduced (status 1); bill 2 is passed (status 4).
    client = _FakeClient({"q": [_search_result(1), _search_result(2)]}, statuses={1: 1, 2: 4})
    store = RadarStore(tmp_path / "radar.json")

    run = run_radar(client, store, queries=("q",))

    ids = {c.bill_id for c in run.new}
    assert ids == {2}  # introduced bill filtered out


def test_relevance_floor_rejects_weak_matches_before_enrichment(tmp_path: Path):
    client = _FakeClient(
        {"q": [_search_result(1, relevance=10), _search_result(2, relevance=90)]},
        statuses={2: 4},  # bill 1 intentionally absent -> would KeyError if enriched
    )
    store = RadarStore(tmp_path / "radar.json")

    run = run_radar(client, store, queries=("q",), relevance_floor=50)

    assert {c.bill_id for c in run.new} == {2}
    # getBill must run on survivors only — bill 1 was never enriched (budget guard).
    assert client.status_calls == [2]


def test_bill_matching_multiple_queries_deduped_highest_relevance(tmp_path: Path):
    client = _FakeClient(
        {
            "q1": [_search_result(1, relevance=40)],
            "q2": [_search_result(1, relevance=95)],
        },
        statuses={1: 4},
    )
    store = RadarStore(tmp_path / "radar.json")

    run = run_radar(client, store, queries=("q1", "q2"), relevance_floor=50)

    assert len(run.new) == 1
    assert run.new[0].relevance == 95  # highest-relevance sighting wins


def test_run_radar_does_not_write_store(tmp_path: Path):
    client = _FakeClient({"q": [_search_result(1)]}, statuses={1: 4})
    store = RadarStore(tmp_path / "radar.json")

    run_radar(client, store, queries=("q",))

    assert store.get(1) is None  # caller commits after opening the issue; radar never writes


# ---------------------------------------------------------------------------
# RadarStore
# ---------------------------------------------------------------------------


def test_radar_store_persist_and_reload(tmp_path: Path):
    p = tmp_path / "radar.json"
    s1 = RadarStore(p)
    s1.set(7, change_hash="abc", first_seen="2026-07-10", issue_number=5)
    s1.save()

    s2 = RadarStore(p)
    entry = s2.get(7)
    assert entry == {"change_hash": "abc", "first_seen": "2026-07-10", "issue_number": 5}


def test_radar_store_missing_returns_none(tmp_path: Path):
    assert RadarStore(tmp_path / "radar.json").get(999) is None


# ---------------------------------------------------------------------------
# LegiScanClient — HTTP plumbing
# ---------------------------------------------------------------------------


def test_get_search_paginates(tmp_path: Path):
    pages = {
        1: {
            "status": "OK",
            "searchresult": {
                "summary": {"page_current": 1, "page_total": 2},
                "0": _search_result(1),
                "1": _search_result(2),
            },
        },
        2: {
            "status": "OK",
            "searchresult": {
                "summary": {"page_current": 2, "page_total": 2},
                "0": _search_result(3),
            },
        },
    }
    client = LegiScanClient("KEY", http_client=_FakeHttp(pages=pages))

    results = client.get_search("artificial intelligence")

    assert [int(r["bill_id"]) for r in results] == [1, 2, 3]


def test_get_search_respects_max_pages(tmp_path: Path):
    pages = {
        1: {
            "status": "OK",
            "searchresult": {
                "summary": {"page_current": 1, "page_total": 9},
                "0": _search_result(1),
            },
        },
    }
    http = _FakeHttp(pages=pages)
    client = LegiScanClient("KEY", http_client=http)

    client.get_search("q", max_pages=1)

    assert [p["page"] for p in http.captured] == [1]  # stopped at the cap, not page_total


def test_get_search_raises_on_non_ok_payload():
    pages = {1: {"status": "ERROR", "alert": {"message": "bad key"}}}
    client = LegiScanClient("KEY", http_client=_FakeHttp(pages=pages))

    with pytest.raises(RuntimeError, match="getSearch"):
        client.get_search("q")


def test_get_bill_status_reads_enum():
    client = LegiScanClient("KEY", http_client=_FakeHttp(bill={"status": 4}))
    assert client.get_bill_status(123) == 4


def test_get_search_sends_key_and_op():
    http = _FakeHttp(pages={1: {"status": "OK", "searchresult": {"summary": {"page_total": 1}}}})
    LegiScanClient("SECRET", http_client=http).get_search("q")

    assert http.captured[0]["key"] == "SECRET"
    assert http.captured[0]["op"] == "getSearch"


# ---------------------------------------------------------------------------
# RadarCandidate
# ---------------------------------------------------------------------------


def test_candidate_status_label():
    c = RadarCandidate.from_search_result(_search_result(1), "q")
    c.status = 4
    assert c.status_label == "passed"
    c.status = 1
    assert c.status_label == "introduced"


def test_candidate_summary_carries_change_hash():
    # Session 2's workflow writes the store from this summary, so change_hash must survive the
    # round-trip (run_radar never writes the store itself — the caller commits after the issue).
    c = RadarCandidate.from_search_result(_search_result(1, change_hash="abc123"), "q")
    c.status = 4
    c.kind = "NEW"
    summary = _candidate_summary(c)
    assert summary["change_hash"] == "abc123"
    assert summary["status"] == "passed"
