"""Eval-harness tests — offline, fast, no embeddings.

Locks the gold set against the real scope screen (the throwaway verify script, now permanent)
and tests the retrieval-metric aggregation with a stub retriever.
"""

from pathlib import Path

from eval.harness import Core
from eval.loader import load_gold
from eval.metrics import score_retrieval, score_scope

from patchwork_assurance.core.scope import load_law_metadata

LAWS = load_law_metadata(Path("corpus"))


def test_gold_loads_and_is_well_formed():
    cases = load_gold()
    assert len(cases) >= 14
    ids = [c.id for c in cases]
    assert len(ids) == len(set(ids)), "gold case ids must be unique"


def test_scope_accuracy_is_perfect_on_gold():
    """The deterministic screen must match every gold verdict. This is the regression lock the
    one-off verify script became: change scope.py or the gold set incompatibly and this fails."""
    core = Core(retriever=None, laws=LAWS)  # scope needs no retriever
    for case in load_gold():
        outcome = score_scope(case, core)
        assert outcome.correct == outcome.total, (
            f"{case.id}: got {outcome.got} != expected {outcome.expected}"
        )


class _Chunk:
    def __init__(self, section_number: str):
        self.section_number = section_number


class _FakeRetriever:
    """Returns canned section numbers per jurisdiction filter — no embeddings, no network."""

    def __init__(self, by_jurisdiction: dict[str, list[str]]):
        self._by = by_jurisdiction

    def retrieve(self, query, filters=None, k=5):
        jurisdiction = filters.jurisdiction if filters else None
        return [_Chunk(s) for s in self._by.get(jurisdiction, [])[:k]]


def _case(case_id: str):
    return next(c for c in load_gold() if c.id == case_id)


def test_retrieval_recall_perfect_when_all_sections_surface():
    core = Core(
        retriever=_FakeRetriever(
            {"Colorado": ["6-1-1704", "6-1-1705"], "Connecticut": ["Sec. 9", "Sec. 10"]}
        ),
        laws=LAWS,
    )
    outcome = score_retrieval(_case("multistate-employment"), core, k=5)
    assert outcome is not None
    assert outcome.recall == 1.0
    assert outcome.missed == []


def test_retrieval_recall_partial_when_a_section_is_missing():
    core = Core(
        retriever=_FakeRetriever(
            {"Colorado": ["6-1-1704", "6-1-1705"], "Connecticut": ["Sec. 9"]}  # Sec. 10 missing
        ),
        laws=LAWS,
    )
    outcome = score_retrieval(_case("multistate-employment"), core, k=5)
    assert outcome is not None
    assert outcome.recall == 0.75
    assert outcome.missed == ["Sec. 10"]


def test_retrieval_skips_out_of_scope_cases():
    core = Core(retriever=_FakeRetriever({}), laws=LAWS)
    assert score_retrieval(_case("no-ai-in-decisions"), core, k=5) is None
