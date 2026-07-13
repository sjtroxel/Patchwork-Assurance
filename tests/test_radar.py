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

import hashlib
from pathlib import Path

import httpx
import pytest

from patchwork_assurance.core.agent.radar import (
    OPENSTATES_BASE,
    LegiScanClient,
    OpenStatesClient,
    RadarCandidate,
    RadarStore,
    _candidate_summary,
    _retry_after_seconds,
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


class _FakeSource:
    """Duck-typed `BillSource` used to drive run_radar (bill_id is a string end-to-end).

    search_results: query -> list of raw getSearch dicts (parsed via from_search_result).
    advanced:       set of bill_id (str) that clear the status floor.
    raises:         set of bill_id (str) whose passes_status_floor raises (transient failure).
    """

    name = "fake"

    def __init__(
        self,
        search_results: dict[str, list[dict]],
        *,
        advanced: set[str],
        raises: set[str] | None = None,
    ) -> None:
        self._search_results = search_results
        self._advanced = advanced
        self._raises = raises or set()
        self.status_calls: list[str] = []

    def search(self, query):
        return [
            RadarCandidate.from_search_result(r, query) for r in self._search_results.get(query, [])
        ]

    def passes_status_floor(self, candidate):
        self.status_calls.append(candidate.bill_id)
        if candidate.bill_id in self._raises:
            raise RuntimeError("transient status-lookup failure")
        if candidate.bill_id in self._advanced:
            candidate.status = 4  # passed
            return True
        candidate.status = 1  # introduced
        return False


class _FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200, headers: dict | None = None) -> None:
        self._payload = payload
        self.status_code = status_code
        self.headers = headers or {}

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
    source = _FakeSource({"artificial intelligence": [_search_result(1)]}, advanced={"1"})
    store = RadarStore(tmp_path / "radar.json")  # empty

    run = run_radar(source, store, queries=("artificial intelligence",))

    assert len(run.new) == 1
    assert run.new[0].kind == "NEW"
    assert run.new[0].bill_id == "1"
    assert run.changed == []


def test_run_radar_changed_hash_carries_issue_number(tmp_path: Path):
    source = _FakeSource({"q": [_search_result(1, change_hash="new-hash")]}, advanced={"1"})
    store = RadarStore(tmp_path / "radar.json")
    store.set("1", change_hash="old-hash", first_seen="2026-07-01", issue_number=42)

    run = run_radar(source, store, queries=("q",))

    assert run.new == []
    assert len(run.changed) == 1
    assert run.changed[0].kind == "CHANGED"
    assert run.changed[0].issue_number == 42  # so the caller can comment on the existing issue


def test_run_radar_unchanged_hash_is_noop(tmp_path: Path):
    source = _FakeSource({"q": [_search_result(1, change_hash="same")]}, advanced={"1"})
    store = RadarStore(tmp_path / "radar.json")
    store.set("1", change_hash="same", first_seen="2026-07-01", issue_number=42)

    run = run_radar(source, store, queries=("q",))

    assert run.new == []
    assert run.changed == []
    assert run.unchanged == 1


# ---------------------------------------------------------------------------
# run_radar — filters
# ---------------------------------------------------------------------------


def test_status_floor_rejects_introduced(tmp_path: Path):
    # bill 1 is introduced (fails the floor); bill 2 is passed.
    source = _FakeSource({"q": [_search_result(1), _search_result(2)]}, advanced={"2"})
    store = RadarStore(tmp_path / "radar.json")

    run = run_radar(source, store, queries=("q",))

    ids = {c.bill_id for c in run.new}
    assert ids == {"2"}  # introduced bill filtered out


def test_relevance_floor_rejects_weak_matches_before_status_floor(tmp_path: Path):
    source = _FakeSource(
        {"q": [_search_result(1, relevance=10), _search_result(2, relevance=90)]},
        advanced={"2"},
    )
    store = RadarStore(tmp_path / "radar.json")

    run = run_radar(source, store, queries=("q",), relevance_floor=50)

    assert {c.bill_id for c in run.new} == {"2"}
    # the status floor must run on survivors only — bill 1 never reached it (budget guard).
    assert source.status_calls == ["2"]


def test_bill_matching_multiple_queries_deduped_highest_relevance(tmp_path: Path):
    source = _FakeSource(
        {
            "q1": [_search_result(1, relevance=40)],
            "q2": [_search_result(1, relevance=95)],
        },
        advanced={"1"},
    )
    store = RadarStore(tmp_path / "radar.json")

    run = run_radar(source, store, queries=("q1", "q2"), relevance_floor=50)

    assert len(run.new) == 1
    assert run.new[0].relevance == 95  # highest-relevance sighting wins


def test_status_lookup_failure_is_isolated_not_fatal(tmp_path: Path):
    # bill 1's status lookup throws (transient hiccup); bill 2 is healthy + passed.
    # The failing bill must not tank the batch: bill 2 still classifies NEW, bill 1 is skipped
    # (unresolved status == don't surface) and counted, so the week's detection survives.
    source = _FakeSource(
        {"q": [_search_result(1), _search_result(2)]},
        advanced={"2"},
        raises={"1"},
    )
    store = RadarStore(tmp_path / "radar.json")

    run = run_radar(source, store, queries=("q",))

    assert {c.bill_id for c in run.new} == {"2"}  # healthy bill still surfaced
    assert run.errors == 1  # failed lookup counted, not raised
    assert source.status_calls == ["1", "2"]  # both checked; only bill 1's raised


def test_run_radar_does_not_write_store(tmp_path: Path):
    source = _FakeSource({"q": [_search_result(1)]}, advanced={"1"})
    store = RadarStore(tmp_path / "radar.json")

    run_radar(source, store, queries=("q",))

    assert store.get("1") is None  # caller commits after opening the issue; radar never writes


# ---------------------------------------------------------------------------
# RadarStore
# ---------------------------------------------------------------------------


def test_radar_store_persist_and_reload(tmp_path: Path):
    p = tmp_path / "radar.json"
    s1 = RadarStore(p)
    s1.set("ocd-bill/xyz", change_hash="abc", first_seen="2026-07-10", issue_number=5)
    s1.save()

    s2 = RadarStore(p)
    entry = s2.get("ocd-bill/xyz")
    assert entry == {"change_hash": "abc", "first_seen": "2026-07-10", "issue_number": 5}


def test_radar_store_missing_returns_none(tmp_path: Path):
    assert RadarStore(tmp_path / "radar.json").get("ocd-bill/nope") is None


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


# ---------------------------------------------------------------------------
# OpenStatesClient — the LegiScan-independent backup source (Session 4)
# ---------------------------------------------------------------------------


def _os_bill(
    bill_id="ocd-bill/abc",
    *,
    identifier="HB 1",
    title="An AI act",
    juris="California",
    updated_at="2026-07-01T00:00:00+00:00",
    classifications=("introduction",),
    latest_passage_date=None,
):
    return {
        "id": bill_id,
        "identifier": identifier,
        "title": title,
        "jurisdiction": {"name": juris},
        "updated_at": updated_at,
        "latest_action_description": "Referred to committee",
        "latest_passage_date": latest_passage_date,
        "openstates_url": f"https://openstates.org/bill/{bill_id}",
        "sources": [{"url": "https://leg.example/bill"}],
        "actions": [{"classification": list(classifications)}],
    }


def _os_page(bills, *, page=1, max_page=1):
    return {"results": list(bills), "pagination": {"page": page, "max_page": max_page}}


class _FakeOSHttp:
    """Fake httpx client: dispatches on URL — the search base vs a per-bill detail path.

    pages: {page_int -> search payload}; bills: {bill_id -> bill dict (with actions) for detail}.
    """

    def __init__(self, pages: dict[int, dict] | None = None, bills: dict[str, dict] | None = None):
        self._pages = pages or {}
        self._bills = bills or {}
        self.captured: list[dict] = []

    def get(self, url, **kwargs):
        params = kwargs["params"]
        self.captured.append({"url": url, **params})
        if url == OPENSTATES_BASE:  # the light full-text search
            return _FakeResponse(self._pages[params["page"]])
        bill_id = url[len(OPENSTATES_BASE) + 1 :]  # detail: base + "/" + bill_id
        return _FakeResponse(self._bills.get(bill_id, {}))


def _os_candidate(bill_id="ocd-bill/abc", title="Artificial Intelligence Act"):
    return RadarCandidate(
        bill_id=bill_id,
        number="HB 1",
        state="California",
        title=title,
        change_hash="h",
        relevance=100,
        url="u",
        query="q",
    )


def test_openstates_parses_bill_into_common_candidate():
    # The LIGHT search leaves `advanced` undecided (None) — status is enriched per-bill later.
    page = _os_page([_os_bill(title="Artificial Intelligence Act")])
    client = OpenStatesClient("KEY", http_client=_FakeOSHttp(pages={1: page}))

    [c] = client.search("artificial intelligence")

    assert c.bill_id == "ocd-bill/abc"  # OCD string id, not an int
    assert c.number == "HB 1"
    assert c.state == "California"
    assert c.url == "https://openstates.org/bill/ocd-bill/abc"
    assert c.relevance == 100  # sentinel — Open States has no relevance score
    assert c.change_hash == hashlib.sha1(b"2026-07-01T00:00:00+00:00").hexdigest()
    assert c.advanced is None  # not decided at search time (no actions in the light response)
    assert c.status_label == "Referred to committee"  # display placeholder from latest_action


def test_openstates_status_floor_fetches_bill_detail_with_actions():
    # passes_status_floor enriches per-bill: hits the /bills/<ocd-id> detail with include=actions.
    detail = _os_bill(classifications=("became-law",))
    http = _FakeOSHttp(bills={"ocd-bill/abc": detail})
    client = OpenStatesClient("KEY", http_client=http)
    c = _os_candidate()

    assert client.passes_status_floor(c) is True
    sent = http.captured[0]
    assert sent["url"] == f"{OPENSTATES_BASE}/ocd-bill/abc"  # single-bill detail endpoint
    assert sent["include"] == "actions"  # the actions the light search deliberately omitted
    assert sent["apikey"] == "KEY"
    assert c.status_label == "became-law"


def test_openstates_introduced_bill_is_not_advanced():
    detail = _os_bill(classifications=("introduction", "referral"))
    client = OpenStatesClient("KEY", http_client=_FakeOSHttp(bills={"ocd-bill/abc": detail}))
    c = _os_candidate()

    assert client.passes_status_floor(c) is False
    assert c.advanced is False


def test_openstates_one_chamber_passage_is_not_advanced():
    # Tuned floor (2026-07-12): bare `passage` (one chamber) and a set latest_passage_date are
    # BOTH excluded — only enrolled/enacted clears. This rejects mid-flight bills that flooded run 1.
    detail = _os_bill(classifications=("passage",), latest_passage_date="2026-06-15")
    client = OpenStatesClient("KEY", http_client=_FakeOSHttp(bills={"ocd-bill/abc": detail}))
    c = _os_candidate()

    assert client.passes_status_floor(c) is False


def test_openstates_enrolled_clears_the_floor():
    detail = _os_bill(classifications=("passage", "enrolled"))
    client = OpenStatesClient("KEY", http_client=_FakeOSHttp(bills={"ocd-bill/abc": detail}))
    c = _os_candidate()

    assert client.passes_status_floor(c) is True
    assert c.status_label == "enrolled"


def test_openstates_title_filter_drops_body_only_matches():
    # Two bills; only one names the query in its title. The body-only match (a budget that merely
    # mentions the phrase) is the dominant noise source the title filter exists to cut — in the LIGHT
    # search, before any per-bill status fetch is spent on it.
    page = _os_page(
        [
            _os_bill(bill_id="ocd-bill/ai", title="Artificial Intelligence Act"),
            _os_bill(bill_id="ocd-bill/budget", title="State Operations Budget"),
        ]
    )
    client = OpenStatesClient("KEY", http_client=_FakeOSHttp(pages={1: page}))  # title match ON

    results = client.search("artificial intelligence")

    assert [c.bill_id for c in results] == ["ocd-bill/ai"]  # body-only budget bill dropped


def test_openstates_title_filter_can_be_disabled():
    page = _os_page(
        [
            _os_bill(bill_id="ocd-bill/ai", title="Artificial Intelligence Act"),
            _os_bill(bill_id="ocd-bill/budget", title="State Operations Budget"),
        ]
    )
    client = OpenStatesClient(
        "KEY", http_client=_FakeOSHttp(pages={1: page}), require_title_match=False
    )

    results = client.search("artificial intelligence")

    assert {c.bill_id for c in results} == {"ocd-bill/ai", "ocd-bill/budget"}


def test_openstates_change_hash_tracks_updated_at():
    a = OpenStatesClient._to_candidate(_os_bill(updated_at="2026-07-01T00:00:00+00:00"), "q")
    b = OpenStatesClient._to_candidate(_os_bill(updated_at="2026-07-08T00:00:00+00:00"), "q")
    same = OpenStatesClient._to_candidate(_os_bill(updated_at="2026-07-01T00:00:00+00:00"), "q")

    assert a.change_hash != b.change_hash  # a record change moves the fingerprint
    assert a.change_hash == same.change_hash  # identical updated_at -> identical fingerprint


def test_openstates_paginates_and_respects_cap():
    pages = {
        1: _os_page([_os_bill(bill_id="ocd-bill/1")], page=1, max_page=2),
        2: _os_page([_os_bill(bill_id="ocd-bill/2")], page=2, max_page=2),
    }
    http = _FakeOSHttp(pages=pages)
    client = OpenStatesClient("KEY", http_client=http, require_title_match=False)

    results = client.search("q")

    assert [c.bill_id for c in results] == ["ocd-bill/1", "ocd-bill/2"]
    assert [p["page"] for p in http.captured] == [1, 2]


def test_openstates_stops_at_max_pages():
    http = _FakeOSHttp(pages={1: _os_page([_os_bill()], page=1, max_page=9)})
    client = OpenStatesClient("KEY", http_client=http, max_pages=1)

    client.search("q")

    assert [p["page"] for p in http.captured] == [1]  # capped, not chased to max_page=9


def test_openstates_search_is_light_no_actions():
    http = _FakeOSHttp(pages={1: _os_page([])})
    OpenStatesClient("SECRET", http_client=http).search("algorithmic discrimination")

    sent = http.captured[0]
    assert sent["url"] == OPENSTATES_BASE
    assert sent["apikey"] == "SECRET"
    assert sent["q"] == "algorithmic discrimination"
    assert sent["classification"] == "bill"  # server-side: drop resolutions (default knob)
    assert "include" not in sent  # LIGHT search — actions are fetched per-bill, not bundled here


def test_openstates_classification_can_be_omitted():
    http = _FakeOSHttp(pages={1: _os_page([])})
    OpenStatesClient("KEY", http_client=http, classification=None).search("q")

    assert "classification" not in http.captured[0]


def test_openstates_non_429_error_raises_immediately():
    class _ErrHttp:
        def get(self, url, **kwargs):
            return _FakeResponse({}, status_code=401)  # auth error — not retryable

    client = OpenStatesClient("KEY", http_client=_ErrHttp())
    with pytest.raises(httpx.HTTPError):
        client.search("q")


class _SeqOSHttp:
    """Fake httpx client returning a preset sequence of responses (drives the retry path)."""

    def __init__(self, responses: list) -> None:
        self._responses = list(responses)
        self.calls = 0

    def get(self, url, **kwargs):
        self.calls += 1
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item  # a queued transport error (e.g. httpx.ReadTimeout)
        return item


def test_openstates_retries_on_429_then_succeeds():
    ok = _os_page([_os_bill(title="Artificial Intelligence Act", classifications=("became-law",))])
    http = _SeqOSHttp(
        [
            _FakeResponse({}, status_code=429, headers={"Retry-After": "3"}),
            _FakeResponse(ok, status_code=200),
        ]
    )
    waits: list[float] = []
    client = OpenStatesClient("KEY", http_client=http, sleep=waits.append)

    results = client.search("artificial intelligence")

    assert [c.bill_id for c in results] == ["ocd-bill/abc"]  # succeeded on the retry
    assert waits == [3.0]  # honored Retry-After, then retried
    assert http.calls == 2


def test_openstates_retries_on_5xx_gateway_then_succeeds():
    # The 2026-07-13 CI failure: Open States' gateway 502'd on one search page. A transient 5xx must
    # be retried (backoff, no Retry-After header), not crash the run.
    ok = _os_page([_os_bill(title="Artificial Intelligence Act")])
    http = _SeqOSHttp([_FakeResponse({}, status_code=502), _FakeResponse(ok, status_code=200)])
    waits: list[float] = []
    client = OpenStatesClient("KEY", http_client=http, sleep=waits.append)

    results = client.search("artificial intelligence")

    assert [c.bill_id for c in results] == ["ocd-bill/abc"]  # recovered on the retry
    assert waits == [1.0]  # backoff 2**0 (5xx carries no Retry-After)
    assert http.calls == 2


def test_openstates_gives_up_after_max_retries():
    http = _SeqOSHttp([_FakeResponse({}, status_code=429) for _ in range(10)])
    waits: list[float] = []
    client = OpenStatesClient("KEY", http_client=http, sleep=waits.append, max_retries=2)

    with pytest.raises(httpx.HTTPError):
        client.search("q")

    assert len(waits) == 2  # retried max_retries times, then raised (no infinite loop)


def test_openstates_retries_on_transport_error_then_succeeds():
    # The 2026-07-13 GitHub-Actions failure: a read-timeout (transport error, raised before any
    # response) must be retried like a 429, not crash the whole run.
    ok = _os_page([_os_bill(title="Artificial Intelligence Act", classifications=("became-law",))])
    http = _SeqOSHttp([httpx.ReadTimeout("read timed out"), _FakeResponse(ok, status_code=200)])
    waits: list[float] = []
    client = OpenStatesClient("KEY", http_client=http, sleep=waits.append)

    results = client.search("artificial intelligence")

    assert [c.bill_id for c in results] == ["ocd-bill/abc"]  # recovered on the retry
    assert waits == [1.0]  # backoff 2**0 (no Retry-After on a timeout)
    assert http.calls == 2


def test_openstates_gives_up_after_transport_retries():
    http = _SeqOSHttp([httpx.ReadTimeout("timeout") for _ in range(10)])
    waits: list[float] = []
    client = OpenStatesClient("KEY", http_client=http, sleep=waits.append, max_retries=2)

    with pytest.raises(httpx.TransportError):
        client.search("q")

    assert len(waits) == 2  # retried max_retries times, then re-raised the timeout


def test_retry_after_seconds_honors_header_else_backoff():
    assert _retry_after_seconds(_FakeResponse({}, 429, headers={"Retry-After": "5"}), 0) == 5.0
    assert _retry_after_seconds(_FakeResponse({}, 429), 3) == 8.0  # no header -> 2**attempt
    assert _retry_after_seconds(_FakeResponse({}, 429, headers={"Retry-After": "999"}), 0) == 30.0
    # A date-form Retry-After isn't parsed as a number -> falls back to backoff.
    date = {"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}
    assert _retry_after_seconds(_FakeResponse({}, 429, headers=date), 1) == 2.0
