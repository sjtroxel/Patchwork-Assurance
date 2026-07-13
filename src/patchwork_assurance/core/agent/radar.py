"""LegiScan radar — national detection layer (Phase 13, Session 1).

Stage 0 in front of the Phase 9 pipeline: discovery of AI-regulation bills *not yet
tracked* across all 50 states + Congress. Phase 9 watches URLs already in the corpus
(url -> hash -> diff -> PR); the radar surfaces *candidates* for human triage, which — once
blessed — flow into the Phase 9 assess/draft/PR lane (or the hand-author lane for codified
titles the fetchers can't reach).

Posture (non-negotiable, see docs/roadmap/phase-13-legiscan-radar.md §2):
  - Candidates only. This module classifies NEW / CHANGED / unchanged and returns them.
    It does NOT open issues, does NOT auto-ingest, does NOT call an LLM. A human gates each one.
  - The store is NOT written here. The caller (Session 2 __main__/workflow) opens the issue,
    records issue_number, then commits — the same save-only-on-success discipline as poll.py,
    so a crashed run never advances the cursor past an unprocessed change.
  - No "we detect every AI law" claim, ever — keyword recall is lossy in both directions.

Status source (Session 2 confirms against the manual): getSearch does not carry a status
enum, so status is enriched via getBill on the relevance-survivors only (budget trivial:
a few dozen getBill calls/week against a 30,000/month free tier). If the manual's search
operators turn out to express a status floor directly, Session 2 can drop the enrichment.

Sources are pluggable behind the `BillSource` seam (Session 4): LegiScan is one adapter,
Open States (open.pluralpolicy.com) is a second. The detection engine, store, dedup,
classification, and workflow are source-agnostic; only the adapter is vendor-specific, so
switching vendors is a one-env-var flip (`RADAR_SOURCE=legiscan|openstates`), not a rewrite.

Public API:
    BillSource               - Protocol: search(query) + passes_status_floor(candidate)
    LegiScanClient           - BillSource over LegiScan getSearch / getBill
    OpenStatesClient         - BillSource over the Open States v3 /bills endpoint
    RadarCandidate           - one detected bill (NEW or CHANGED); bill_id is a string
    RadarStore               - rich per-bill store (change_hash, first_seen, issue_number)
    run_radar(source, store) - search -> filter -> status-floor -> classify; returns a RadarRun
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

import httpx

# LegiScan REST base; every op is a query-string on this URL (op=getSearch, op=getBill, ...).
LEGISCAN_BASE = "https://api.legiscan.com/"

# Reuse poll.py's fetch discipline so detection and the Phase 9 fetch stay consistent.
from patchwork_assurance.core.agent.poll import REQUEST_HEADERS  # noqa: E402

# Seed queries — 4 to start, tuned from false positives in Session 2 (doc §6 decision 1).
RADAR_QUERIES: tuple[str, ...] = (
    "artificial intelligence",
    "automated decision",
    "algorithmic discrimination",
    "automated employment decision",
)

# LegiScan bill status enum (API manual v1.91). We gate on laws that have actually advanced;
# introduced bills (status 1) are thousands per session and nearly all die — the status floor
# is what keeps the radar signal from drowning in them (doc §2, §6 decision 4).
STATUS_LABELS: dict[int, str] = {
    1: "introduced",
    2: "engrossed",
    3: "enrolled",
    4: "passed",
    5: "vetoed",
    6: "failed",
}
PASSED_STATUSES: frozenset[int] = frozenset({3, 4})  # enrolled / passed(=signed into law)

# Defaults; both tuned in Session 2 from the first real batch (doc §5 step 6).
DEFAULT_RELEVANCE_FLOOR = 50
MAX_PAGES = 5  # budget guard: getSearch paginates ~50/page; 5 pages/query is plenty


# ---------------------------------------------------------------------------
# Source seam — the one vendor-specific surface (doc §12)
# ---------------------------------------------------------------------------


class BillSource(Protocol):
    """A pluggable bill data source. Everything else in run_radar is source-agnostic.

    Two operations vary by vendor: how a search result maps to a common `RadarCandidate`,
    and how "advanced enough" (the status floor) is decided — a network call for LegiScan
    (getBill), a local read of already-fetched actions for Open States.
    """

    name: str

    def search(self, query: str) -> list[RadarCandidate]:
        """Full-text search this source; return parsed candidates (not raw dicts)."""
        ...

    def passes_status_floor(self, candidate: RadarCandidate) -> bool:
        """Whether the bill has advanced to enrolled/passed. May hit the network."""
        ...


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class LegiScanClient:
    """`BillSource` over the LegiScan REST API (getSearch + getBill only).

    Mirrors poll.py: an httpx client may be injected for tests; the browser-ish
    User-Agent and timeout discipline are shared. No LLM, no state. Search config
    (state / year / page cap) lives on the instance so `search(query)` matches the
    source-agnostic `BillSource` signature.
    """

    name = "legiscan"

    def __init__(
        self,
        api_key: str,
        *,
        http_client: httpx.Client | None = None,
        state: str = "ALL",
        year: int | None = None,
        max_pages: int = MAX_PAGES,
    ) -> None:
        self._api_key = api_key
        self._client = http_client
        self._state = state
        self._year = year
        self._max_pages = max_pages

    def _get(self, op: str, **params: object) -> dict:
        fetch = self._client.get if self._client else httpx.get
        response = fetch(
            LEGISCAN_BASE,
            params={"key": self._api_key, "op": op, **params},
            timeout=30.0,
            headers=REQUEST_HEADERS,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") != "OK":
            raise RuntimeError(f"LegiScan {op} returned status={payload.get('status')!r}")
        return payload

    def get_search(
        self, query: str, *, state: str = "ALL", year: int | None = None, max_pages: int = MAX_PAGES
    ) -> list[dict]:
        """Full-text search across `state` (ALL = 50 states + Congress). Returns raw result dicts.

        Paginates up to max_pages (a budget guard). Each result carries LegiScan's canonical
        `change_hash` — the dedup primitive — plus `relevance`, `bill_id`, `bill_number`, `state`.
        """
        results: list[dict] = []
        page = 1
        while page <= max_pages:
            params: dict[str, object] = {"state": state, "query": query, "page": page}
            if year is not None:
                params["year"] = year
            searchresult = self._get("getSearch", **params).get("searchresult", {})
            # searchresult is {"summary": {...}, "0": {...bill...}, "1": {...}, ...}.
            summary = searchresult.get("summary", {})
            results.extend(v for k, v in searchresult.items() if k.isdigit())
            page_total = int(summary.get("page_total", page))
            if page >= page_total:
                break
            page += 1
        return results

    def get_bill_status(self, bill_id: int) -> int | None:
        """Return the LegiScan status enum for a bill (via getBill), or None if absent."""
        bill = self._get("getBill", id=bill_id).get("bill", {})
        status = bill.get("status")
        return int(status) if status is not None else None

    # --- BillSource interface -------------------------------------------------

    def search(self, query: str) -> list[RadarCandidate]:
        """Search LegiScan and parse each result into a common `RadarCandidate`."""
        return [
            RadarCandidate.from_search_result(r, query)
            for r in self.get_search(
                query, state=self._state, year=self._year, max_pages=self._max_pages
            )
        ]

    def passes_status_floor(self, candidate: RadarCandidate) -> bool:
        """Enrich status via getBill (the network call), then apply the enrolled/passed floor.

        getSearch carries no status enum, so LegiScan resolves it lazily here — one getBill per
        relevance-survivor. A raise propagates to run_radar's per-bill isolation (Session 3).
        """
        candidate.status = self.get_bill_status(int(candidate.bill_id))
        return candidate.status in PASSED_STATUSES


# ---------------------------------------------------------------------------
# Open States client — the LegiScan-independent backup source (doc §12)
# ---------------------------------------------------------------------------

# Open States v3 full-text bill search. Auth is an X-API-KEY header (or ?apikey); a self-serve
# free key (open.pluralpolicy.com) covers all 50 states + DC + PR — no federal, which the radar
# does not want (federal is a preemption fight, out of scope; the patchwork is the states).
OPENSTATES_BASE = "https://v3.openstates.org/bills"

# Open States has no status enum. "Advanced" is read from the bill's action classifications
# (controlled vocab). Tuned from the first real batch (2026-07-12): this is the enrolled/enacted
# floor, matching LegiScan's enrolled(3)/passed(4) - bare one-chamber `passage` is deliberately
# EXCLUDED (it flooded the first run with mid-flight bills). enrolled = passed both chambers;
# became-law / executive-signature = enacted.
OPENSTATES_PASSED_CLASSIFICATIONS: frozenset[str] = frozenset(
    {"enrolled", "became-law", "executive-signature"}
)
OPENSTATES_PER_PAGE = 20  # response carries a pagination.max_page; we still cap at MAX_PAGES
OPENSTATES_MAX_BACKOFF = 30.0  # cap a single wait so a large Retry-After can't hang the run
# Statuses worth retrying: 429 rate-limit + transient gateway/server errors. Open States' gateway
# intermittently 502/504s on our queries from CI (2026-07-13) — one flaky page shouldn't tank the run.
RETRIABLE_STATUSES: frozenset[int] = frozenset({429, 500, 502, 503, 504})
# Open States can be slow to answer from cloud/CI IPs (GitHub runners read-timed-out at 30s on
# 2026-07-13 while a residential IP was fine). Give the read phase generous room so a slow-but-alive
# server can finish "at its leisure"; keep connect tight so a truly dead connection still fails fast.
# The hard backstop against a *hung* (never-responding) connection is the workflow job's
# `timeout-minutes`, not this — a request timeout can't tell "slow" from "hung", only a job cap can.
OPENSTATES_TIMEOUT = httpx.Timeout(15.0, read=90.0)


def _retry_after_seconds(response: httpx.Response, attempt: int) -> float:
    """Seconds to wait before retrying a 429: honor a numeric Retry-After, else exponential backoff."""
    header = response.headers.get("Retry-After")
    if header:
        try:
            return min(float(header), OPENSTATES_MAX_BACKOFF)
        except ValueError:
            pass  # Retry-After can be an HTTP-date; fall back to backoff rather than parse it
    return min(2.0**attempt, OPENSTATES_MAX_BACKOFF)


class OpenStatesClient:
    """`BillSource` over the Open States v3 `/bills` endpoint.

    Two-step like LegiScan: a LIGHT full-text search (no `include=actions`) returns candidates, then
    the status floor is enriched per-survivor via a small per-bill fetch in passes_status_floor.
    (Bundling actions into the broad search 504'd Open States' gateway from CI on 2026-07-13 — the
    heavy response was too much for their backend; the per-bill fetch is a tiny request that isn't.)
    Open States exposes no relevance score, so `relevance` is a sentinel and the shared relevance
    floor is a no-op; precision comes from three knobs tuned against the first real batch:
    `classification="bill"` (drop resolutions), `require_title_match` (query phrase must be in the
    title, not just the body — also the budget guard that bounds the per-bill fetches), and the
    enrolled/enacted status floor. Trade-off: the title match favors precision, so a bill titled with
    only the abbreviation (e.g. "...-AI") can be missed until it surfaces another way - acceptable for
    a human-gated radar, revisit if recall matters.
    """

    name = "openstates"

    def __init__(
        self,
        api_key: str,
        *,
        http_client: httpx.Client | None = None,
        per_page: int = OPENSTATES_PER_PAGE,
        max_pages: int = MAX_PAGES,
        action_since: str | None = None,
        classification: str | None = "bill",
        require_title_match: bool = True,
        max_retries: int = 4,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._api_key = api_key
        self._client = http_client
        self._per_page = per_page
        self._max_pages = max_pages
        self._action_since = action_since  # e.g. "2026-04-01" to focus on freshly-advanced bills
        # Precision knobs, tuned from the first real batch (2026-07-12), which returned 126 candidates
        # ~65% noise: full-text `q` matches any body mention (budgets, omnibus, ferry audits).
        self._classification = (
            classification  # server-side: "bill" drops study/memorial resolutions
        )
        self._require_title_match = (
            require_title_match  # client-side: query phrase must be in the title
        )
        # Open States' free tier rate-limits (429); ride it out with bounded backoff instead of
        # crashing the run (sleep is injectable so tests don't actually wait).
        self._max_retries = max_retries
        self._sleep = sleep

    def _request(self, url: str, params: dict) -> dict:
        fetch = self._client.get if self._client else httpx.get
        full = {**params, "apikey": self._api_key}
        for attempt in range(self._max_retries + 1):
            # A transport error (ReadTimeout / ConnectError / ...) is raised *before* any response
            # and is transient — retry it with backoff, just like a 429, instead of crashing the run.
            # (Real GitHub-Actions failure 2026-07-13: Open States read-timed-out from the runner and
            # the whole radar crashed because only 429 *status codes* were retried, not timeouts.)
            try:
                response = fetch(
                    url,
                    params=full,
                    timeout=OPENSTATES_TIMEOUT,
                    headers=REQUEST_HEADERS,
                )
            except httpx.TransportError:
                if attempt < self._max_retries:
                    self._sleep(min(2.0**attempt, OPENSTATES_MAX_BACKOFF))
                    continue
                raise
            # 429 and transient gateway/server 5xx (502/503/504) are retryable — honor Retry-After if
            # present, else exponential backoff (1, 2, 4, ... capped at 30s), then retry. Any other
            # error (401 auth, 404, ...) raises immediately.
            if response.status_code in RETRIABLE_STATUSES and attempt < self._max_retries:
                self._sleep(_retry_after_seconds(response, attempt))
                continue
            response.raise_for_status()  # Open States signals errors via HTTP status, not an envelope
            return response.json()
        # Unreachable in practice (the last attempt returns or raises above); kept for type safety.
        raise RuntimeError("Open States request retries exhausted")  # pragma: no cover

    def search(self, query: str) -> list[RadarCandidate]:
        """Full-text search across all jurisdictions; parse each bill into a `RadarCandidate`.

        Applies the precision knobs: `classification` filters server-side (drop resolutions), and
        `require_title_match` drops body-only matches whose title doesn't contain the query phrase
        (the dominant noise source — a passing mention in a budget or omnibus bill).
        """
        needle = query.lower()
        results: list[RadarCandidate] = []
        page = 1
        while page <= self._max_pages:
            # LIGHT search: NO include=actions. Bundling every result's action history into one broad
            # full-text response is what timed out Open States' gateway (504) from CI on 2026-07-13.
            # Status is enriched per-survivor in passes_status_floor instead (mirrors LegiScan's getBill).
            params: dict[str, object] = {
                "q": query,
                "sort": "latest_action_desc",
                "page": page,
                "per_page": self._per_page,
            }
            if self._classification:
                params["classification"] = self._classification
            if self._action_since:
                params["action_since"] = self._action_since
            payload = self._request(OPENSTATES_BASE, params)
            for bill in payload.get("results", []):
                candidate = self._to_candidate(bill, query)
                if self._require_title_match and needle not in candidate.title.lower():
                    continue  # body-only mention (budget/omnibus noise) — not a candidate
                results.append(candidate)
            pagination = payload.get("pagination", {})
            max_page = int(pagination.get("max_page", page))
            if page >= max_page:
                break
            page += 1
        return results

    @staticmethod
    def _to_candidate(bill: dict, query: str) -> RadarCandidate:
        # Parsed from the LIGHT search response (no actions), so `advanced` is left None here and
        # decided later by passes_status_floor's per-bill fetch. status_text is a display placeholder.
        jurisdiction = bill.get("jurisdiction") or {}
        sources = bill.get("sources") or []
        url = bill.get("openstates_url") or (sources[0].get("url") if sources else "")
        # Open States has no change_hash; updated_at bumps on any record change -> hash it as the
        # opaque per-source change fingerprint the store dedups on.
        updated_at = str(bill.get("updated_at", ""))
        change_hash = hashlib.sha1(updated_at.encode()).hexdigest() if updated_at else ""
        return RadarCandidate(
            bill_id=str(bill.get("id", "")),
            number=str(bill.get("identifier", "")),
            state=str(jurisdiction.get("name", "")),
            title=str(bill.get("title", "")),
            change_hash=change_hash,
            relevance=100,  # no score from Open States; relevance floor is a no-op here
            url=str(url),
            query=query,
            status_text=(str(bill.get("latest_action_description", "")) or "in progress")[:40],
        )

    @staticmethod
    def _advanced_from_actions(bill: dict) -> tuple[bool, str | None]:
        """(advanced, label) from a bill's action classifications, per the enrolled/enacted floor.

        A set `latest_passage_date` (one-chamber passage) is deliberately NOT advanced (tuned
        2026-07-12 — it re-admitted mid-flight bills).
        """
        actions = bill.get("actions") or []
        classifications = {c for a in actions for c in (a.get("classification") or [])}
        passed = classifications & OPENSTATES_PASSED_CLASSIFICATIONS
        return (bool(passed), sorted(passed)[0] if passed else None)

    def passes_status_floor(self, candidate: RadarCandidate) -> bool:
        """Enrich status via a LIGHT per-bill fetch (one bill's actions), then apply the floor.

        The broad search is deliberately actions-free (it 504'd their gateway); the enrolled/enacted
        decision needs action classifications, so we fetch them one bill at a time here — a small,
        fast request that won't choke the backend. Called only on relevance/title survivors, so it's
        a bounded handful of calls. Mirrors LegiScan's getBill enrichment. A raise (timeout/429 past
        retries) propagates to run_radar's per-bill isolation.
        """
        # candidate.bill_id is the OCD id "ocd-bill/<uuid>"; the detail endpoint is base + that id.
        bill = self._request(f"{OPENSTATES_BASE}/{candidate.bill_id}", {"include": "actions"})
        advanced, label = self._advanced_from_actions(bill)
        candidate.advanced = advanced
        if label:
            candidate.status_text = label
        return advanced


# ---------------------------------------------------------------------------
# Candidate
# ---------------------------------------------------------------------------


@dataclass
class RadarCandidate:
    """One detected bill. `kind` is set by run_radar after dedup vs the store.

    `bill_id` is a **string** so it can hold both LegiScan's integer ids (stringified,
    losslessly) and Open States' OCD ids (`ocd-bill/...`). `change_hash` is an opaque
    per-source change fingerprint (LegiScan's canonical change_hash; a hash of Open States'
    `updated_at`). `relevance` is source-provided or a sentinel (Open States has no score).
    """

    bill_id: str
    number: str
    state: str
    title: str
    change_hash: str
    relevance: int
    url: str
    query: str
    status: int | None = None  # LegiScan status enum; None for sources without one
    status_text: str | None = None  # normalized status label when there is no enum (Open States)
    advanced: bool | None = None  # status-floor result cached by sources that decide at search time
    kind: str = ""  # "NEW" | "CHANGED", filled by run_radar
    issue_number: int | None = None  # carried on CHANGED so the caller can comment

    @classmethod
    def from_search_result(cls, result: dict, query: str) -> RadarCandidate:
        return cls(
            bill_id=str(result["bill_id"]),
            number=str(result.get("bill_number", "")),
            state=str(result.get("state", "")),
            title=str(result.get("title", "")),
            change_hash=str(result.get("change_hash", "")),
            relevance=int(result.get("relevance", 0)),
            url=str(result.get("url", "")),
            query=query,
        )

    @property
    def status_label(self) -> str:
        if self.status_text is not None:
            return self.status_text
        return STATUS_LABELS.get(self.status or 0, "unknown")


# ---------------------------------------------------------------------------
# Store — rich per-bill value, save-only-on-success (mirrors store.HashStore)
# ---------------------------------------------------------------------------


class RadarStore:
    """Per-bill radar state: {bill_id -> {change_hash, first_seen, issue_number}}.

    JSON keys are strings (bill_id stringified). Written only on explicit save(), so a failed
    run never advances past an unprocessed change — the exact discipline HashStore uses.
    """

    def __init__(self, path: Path | str) -> None:
        self._path = Path(path)
        self._data: dict[str, dict] = {}
        if self._path.exists():
            self._data = json.loads(self._path.read_text())

    def get(self, bill_id: str) -> dict | None:
        return self._data.get(str(bill_id))

    def set(
        self, bill_id: str, *, change_hash: str, first_seen: str, issue_number: int | None
    ) -> None:
        self._data[str(bill_id)] = {
            "change_hash": change_hash,
            "first_seen": first_seen,
            "issue_number": issue_number,
        }

    def save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(self._data, indent=2))


# ---------------------------------------------------------------------------
# Detection run
# ---------------------------------------------------------------------------


@dataclass
class RadarRun:
    new: list[RadarCandidate] = field(default_factory=list)
    changed: list[RadarCandidate] = field(default_factory=list)
    unchanged: int = 0
    # Survivors whose getBill status lookup raised (network/HTTP/non-OK). Counted, not fatal:
    # a single flaky enrichment must not tank the whole weekly batch. Skipped conservatively
    # (no status == don't surface), so the bill re-appears next run once LegiScan is healthy.
    errors: int = 0


def run_radar(
    source: BillSource,
    store: RadarStore,
    *,
    queries: tuple[str, ...] = RADAR_QUERIES,
    relevance_floor: int = DEFAULT_RELEVANCE_FLOOR,
) -> RadarRun:
    """Search -> relevance floor -> status floor -> dedup/classify. Source-agnostic.

    Returns NEW / CHANGED candidates and an unchanged count. Does NOT write the store: the
    caller opens the issue (recording issue_number) and commits, mirroring poll's discipline.

    A bill matching several queries is de-duplicated within the run (highest relevance wins).
    Per-source specifics (result parsing, how the status floor is decided) live behind `source`.
    """
    # 1. Search every query; collect unique bills (keep the highest-relevance sighting).
    by_bill: dict[str, RadarCandidate] = {}
    for query in queries:
        for candidate in source.search(query):
            existing = by_bill.get(candidate.bill_id)
            if existing is None or candidate.relevance > existing.relevance:
                by_bill[candidate.bill_id] = candidate

    # 2. Relevance floor first — cheap, and it bounds the status-floor budget (a no-op for
    #    sources without a relevance score, e.g. Open States, whose candidates score a sentinel).
    survivors = [c for c in by_bill.values() if c.relevance >= relevance_floor]

    # 3. Apply the status floor via the source (a network getBill for LegiScan; a local read for
    #    Open States), then classify survivors that clear it.
    run = RadarRun()
    for candidate in survivors:
        # A per-bill status lookup that raises is isolated: one transient hiccup skips that
        # candidate (counted in run.errors) rather than crashing the batch and losing the
        # week's already-classified bills. The skip is safe — unresolved status means we don't
        # surface it — and the bill returns on the next weekly run once the API is healthy again.
        try:
            if not source.passes_status_floor(candidate):
                continue
        except (httpx.HTTPError, RuntimeError, ValueError):
            run.errors += 1
            continue

        # 4. Dedup / classify vs the store on (bill_id, change_hash).
        prior = store.get(candidate.bill_id)
        if prior is None:
            candidate.kind = "NEW"
            run.new.append(candidate)
        elif prior.get("change_hash") != candidate.change_hash:
            candidate.kind = "CHANGED"
            candidate.issue_number = prior.get("issue_number")
            run.changed.append(candidate)
        else:
            run.unchanged += 1

    return run


# ---------------------------------------------------------------------------
# Entrypoint — python -m patchwork_assurance.core.agent.radar
# ---------------------------------------------------------------------------


def _candidate_summary(c: RadarCandidate) -> dict:
    # change_hash is included so Session 2's workflow can write it into the store after opening
    # the issue — run_radar deliberately does not write the store (poll discipline), so the hash
    # must round-trip through this summary for the caller to commit it.
    return {
        "bill_id": c.bill_id,
        "number": c.number,
        "state": c.state,
        "title": c.title,
        "status": c.status_label,
        "relevance": c.relevance,
        "url": c.url,
        "query": c.query,
        "kind": c.kind,
        "change_hash": c.change_hash,
        "issue_number": c.issue_number,
    }


def _build_source(source_name: str, env: dict) -> BillSource:
    """Build the configured BillSource from the environment, or raise KeyError if its key is unset."""
    if source_name == "openstates":
        api_key = env.get("OPENSTATES_API_KEY")
        if not api_key:
            raise KeyError("OPENSTATES_API_KEY is not set")
        return OpenStatesClient(api_key, action_since=env.get("RADAR_ACTION_SINCE"))
    api_key = env.get("LEGISCAN_API_KEY")
    if not api_key:
        raise KeyError("LEGISCAN_API_KEY is not set")
    year_env = env.get("RADAR_YEAR")
    return LegiScanClient(api_key, year=int(year_env) if year_env else None)


def main() -> None:
    """Run the radar and print a JSON summary to stdout.

    Detection only — emits NEW/CHANGED candidates. The workflow reads this summary, opens/updates
    issues via gh, and commits the store with each issue_number. The source is pluggable: whichever
    vendor's key is available finishes the phase, selected by RADAR_SOURCE.

    Environment:
      RADAR_SOURCE       legiscan (default) | openstates
      LEGISCAN_API_KEY   required when RADAR_SOURCE=legiscan (free tier, 30,000 req/month)
      OPENSTATES_API_KEY required when RADAR_SOURCE=openstates (self-serve free key)
      RADAR_STORE_PATH   rich per-bill store (default: .radar_store.json)
      RADAR_YEAR         LegiScan search year (default: unset -> current-session default)
      RADAR_ACTION_SINCE Open States: only bills with an action since this date (e.g. 2026-04-01)
    """
    import os
    import sys

    source_name = os.environ.get("RADAR_SOURCE", "legiscan").lower()
    try:
        source = _build_source(source_name, dict(os.environ))
    except KeyError as exc:
        print(str(exc.args[0]), file=sys.stderr)
        sys.exit(1)

    store = RadarStore(os.environ.get("RADAR_STORE_PATH", ".radar_store.json"))
    run = run_radar(source, store)

    summary = {
        "source": source.name,
        "total_new": len(run.new),
        "total_changed": len(run.changed),
        "total_unchanged": run.unchanged,
        "total_errors": run.errors,  # status lookups that failed and were skipped (not fatal)
        "new": [_candidate_summary(c) for c in run.new],
        "changed": [_candidate_summary(c) for c in run.changed],
    }
    print(json.dumps(summary, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
