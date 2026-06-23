"""Deterministic eval metrics — Tier A: free, offline, no API key.

Scope accuracy and retrieval hit-rate. The judged metrics (citation groundedness, obligation
coverage) are Tier B, wired later behind a flag (phase-6 IMPLEMENTATION §6) because they spend
API tokens.
"""

from dataclasses import dataclass

from eval.harness import Core
from eval.loader import GoldCase
from patchwork_assurance.core.memo import _focus  # production query builder — see note below
from patchwork_assurance.core.retrieval import RetrievalFilters
from patchwork_assurance.core.scope import applicable_laws

_IN_SCOPE = ("yes", "uncertain")

# We import memo._focus on purpose: the retrieval metric must query with the EXACT string the
# memo path uses, or it would measure a different path than production (the whole point of the
# harness). _focus is module-private today; promoting it to a public helper is a clean future tidy.


@dataclass
class ScopeOutcome:
    case_id: str
    got: dict[str, str]  # law_id -> verdict the screen produced
    expected: dict[str, str]
    correct: int
    total: int


def score_scope(case: GoldCase, core: Core) -> ScopeOutcome:
    """Run the real scope screen and compare every per-law verdict to the gold answer."""
    got = {r.law_id: r.in_scope for r in applicable_laws(case.situation, core.laws)}
    expected = case.expect.scope
    correct = sum(1 for law_id, want in expected.items() if got.get(law_id) == want)
    return ScopeOutcome(case.id, got, expected, correct, len(expected))


@dataclass
class RetrievalOutcome:
    case_id: str
    want: list[str]
    hit: list[str]
    missed: list[str]
    recall: float


def score_retrieval(case: GoldCase, core: Core, k: int) -> RetrievalOutcome | None:
    """Retrieve per in-scope jurisdiction (mirroring memo.generate_memo's filtered retrieve) and
    check which gold grounding sections were surfaced in the top-k. Returns None for out-of-scope
    cases (no grounding to score)."""
    want = case.expect.grounding_sections
    if not want:
        return None
    query = _focus(case.situation)
    retrieved: set[str] = set()
    for result in applicable_laws(case.situation, core.laws):
        if result.in_scope in _IN_SCOPE:
            chunks = core.retriever.retrieve(
                query, RetrievalFilters(jurisdiction=result.jurisdiction), k=k
            )
            retrieved |= {c.section_number for c in chunks}
    hit = [s for s in want if s in retrieved]
    missed = [s for s in want if s not in retrieved]
    return RetrievalOutcome(case.id, want, hit, missed, len(hit) / len(want))
