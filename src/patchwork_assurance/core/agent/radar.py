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

Public API:
    LegiScanClient           - thin httpx wrapper over getSearch / getBill
    RadarCandidate           - one detected bill (NEW or CHANGED)
    RadarStore               - rich per-bill store (change_hash, first_seen, issue_number)
    run_radar(client, store) - search -> filter -> enrich -> classify; returns a RadarRun
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

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
# Client
# ---------------------------------------------------------------------------


class LegiScanClient:
    """Thin wrapper over the LegiScan REST API (getSearch + getBill only).

    Mirrors poll.py: an httpx client may be injected for tests; the browser-ish
    User-Agent and timeout discipline are shared. No LLM, no state.
    """

    def __init__(self, api_key: str, *, http_client: httpx.Client | None = None) -> None:
        self._api_key = api_key
        self._client = http_client

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


# ---------------------------------------------------------------------------
# Candidate
# ---------------------------------------------------------------------------


@dataclass
class RadarCandidate:
    """One detected bill. `kind` is set by run_radar after dedup vs the store."""

    bill_id: int
    number: str
    state: str
    title: str
    change_hash: str
    relevance: int
    url: str
    query: str
    status: int | None = None
    kind: str = ""  # "NEW" | "CHANGED", filled by run_radar
    issue_number: int | None = None  # carried on CHANGED so the caller can comment

    @classmethod
    def from_search_result(cls, result: dict, query: str) -> RadarCandidate:
        return cls(
            bill_id=int(result["bill_id"]),
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

    def get(self, bill_id: int) -> dict | None:
        return self._data.get(str(bill_id))

    def set(
        self, bill_id: int, *, change_hash: str, first_seen: str, issue_number: int | None
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


def run_radar(
    client: LegiScanClient,
    store: RadarStore,
    *,
    queries: tuple[str, ...] = RADAR_QUERIES,
    relevance_floor: int = DEFAULT_RELEVANCE_FLOOR,
    year: int | None = None,
    max_pages: int = MAX_PAGES,
) -> RadarRun:
    """Search -> relevance floor -> status enrich -> status floor -> dedup/classify.

    Returns NEW / CHANGED candidates and an unchanged count. Does NOT write the store: the
    caller opens the issue (recording issue_number) and commits, mirroring poll's discipline.

    A bill matching several queries is de-duplicated within the run (highest relevance wins).
    """
    # 1. Search every query; collect unique bills (keep the highest-relevance sighting).
    by_bill: dict[int, RadarCandidate] = {}
    for query in queries:
        for result in client.get_search(query, year=year, max_pages=max_pages):
            candidate = RadarCandidate.from_search_result(result, query)
            existing = by_bill.get(candidate.bill_id)
            if existing is None or candidate.relevance > existing.relevance:
                by_bill[candidate.bill_id] = candidate

    # 2. Relevance floor first — cheap, and it bounds the getBill enrichment budget.
    survivors = [c for c in by_bill.values() if c.relevance >= relevance_floor]

    # 3. Enrich status (getBill) on survivors only, then apply the status floor.
    run = RadarRun()
    for candidate in survivors:
        candidate.status = client.get_bill_status(candidate.bill_id)
        if candidate.status not in PASSED_STATUSES:
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
        "issue_number": c.issue_number,
    }


def main() -> None:
    """Run the radar and print a JSON summary to stdout.

    Session 1: detection only — emits NEW/CHANGED candidates. Session 2's workflow reads this
    summary, opens/updates issues via gh, and commits the store with each issue_number.

    Environment:
      LEGISCAN_API_KEY   required (free tier, 30,000 req/month)
      RADAR_STORE_PATH   rich per-bill store (default: .radar_store.json)
      RADAR_YEAR         search year (default: unset -> LegiScan's current-session default)
    """
    import os
    import sys

    api_key = os.environ.get("LEGISCAN_API_KEY")
    if not api_key:
        print("LEGISCAN_API_KEY is not set", file=sys.stderr)
        sys.exit(1)

    store = RadarStore(os.environ.get("RADAR_STORE_PATH", ".radar_store.json"))
    year_env = os.environ.get("RADAR_YEAR")
    run = run_radar(
        LegiScanClient(api_key),
        store,
        year=int(year_env) if year_env else None,
    )

    summary = {
        "total_new": len(run.new),
        "total_changed": len(run.changed),
        "total_unchanged": run.unchanged,
        "new": [_candidate_summary(c) for c in run.new],
        "changed": [_candidate_summary(c) for c in run.changed],
    }
    print(json.dumps(summary, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
