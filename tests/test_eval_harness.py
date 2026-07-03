"""Eval-harness tests — offline, fast, no embeddings.

Locks the gold set against the real scope screen (the throwaway verify script, now permanent)
and tests the retrieval-metric aggregation with a stub retriever.
"""

from pathlib import Path

from eval.harness import Core
from eval.judge import JudgeVerdict, score_groundedness
from eval.loader import RetrievalQueryCase, load_gold, load_retrieval_gold
from eval.metrics import (
    score_citation_exists,
    score_coverage,
    score_query_retrieval,
    score_retrieval,
    score_scope,
)
from eval.safety import confirm_spend

from patchwork_assurance.core.contracts import ComplianceMemo, LawFinding, MemoObligation
from patchwork_assurance.core.grounding import corpus_section_texts, locate_section
from patchwork_assurance.core.scope import load_law_metadata

LAWS = load_law_metadata(Path("corpus"))
SECTION_TEXTS = corpus_section_texts(Path("corpus"))
SECTIONS = {jurisdiction: set(texts) for jurisdiction, texts in SECTION_TEXTS.items()}


def test_gold_loads_and_is_well_formed():
    cases = load_gold()
    assert len(cases) >= 14
    ids = [c.id for c in cases]
    assert len(ids) == len(set(ids)), "gold case ids must be unique"


def test_retrieval_gold_loads_and_is_well_formed():
    cases = load_retrieval_gold()
    assert len(cases) >= 5
    ids = [c.id for c in cases]
    assert len(ids) == len(set(ids)), "retrieval gold ids must be unique"
    assert all(c.query and c.grounding_sections for c in cases), (
        "each case needs a query + sections"
    )


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
    def __init__(self, section_number: str, chunk_index: int):
        self.section_number = section_number
        self.chunk_index = chunk_index


class _FakeRetriever:
    """Returns canned section numbers per filter key — no embeddings, no network. The key is the
    law_id when set (the memo/scope-recall path) else the jurisdiction (the exact-term query path).
    chunk_index = the section's position in the law's canned list, so it is stable across the top-k
    call and the key-obligation pin's per-section refetch (dedup by chunk_index then works). Honors
    filters.section_number so the pin's section-scoped retrieve returns only that section (or nothing
    when the canned list doesn't hold it — mirroring a section that isn't indexed)."""

    def __init__(self, by_key: dict[str, list[str]]):
        self._by = by_key

    def retrieve(self, query, filters=None, k=5):
        key = (filters.law_id or filters.jurisdiction) if filters else None
        pairs = list(enumerate(self._by.get(key, [])))
        if filters and filters.section_number:
            pairs = [(i, s) for i, s in pairs if s == filters.section_number]
        return [_Chunk(s, i) for i, s in pairs[:k]]

    def query(self, query, filters=None, k=5, mode="filtered"):
        # The metric routes through query() (Phase 8); the fake has no lexical index, so filtered
        # and hybrid both reduce to the canned filtered retrieve.
        return self.retrieve(query, filters, k)


def _case(case_id: str):
    return next(c for c in load_gold() if c.id == case_id)


def test_retrieval_recall_perfect_when_all_sections_surface():
    core = Core(
        retriever=_FakeRetriever(
            {"co-sb26-189": ["6-1-1704", "6-1-1705"], "ct-sb5-pa26-15": ["Sec. 9", "Sec. 10"]}
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
            {
                "co-sb26-189": ["6-1-1704", "6-1-1705"],
                "ct-sb5-pa26-15": ["Sec. 9"],
            }  # Sec. 10 missing
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


def test_query_retrieval_scores_exact_term_case():
    # Exact-term metric: query the (faked) corpus and check the cited section surfaced. The fake
    # returns canned sections per jurisdiction, so this locks the metric wiring, not the model.
    core = Core(retriever=_FakeRetriever({"Colorado": ["6-1-1704", "6-1-1703"]}), laws=LAWS)
    case = RetrievalQueryCase(
        id="q", query="section 6-1-1704?", jurisdiction="Colorado", grounding_sections=["6-1-1704"]
    )
    outcome = score_query_retrieval(case, core, k=5, mode="hybrid")
    assert outcome.recall == 1.0 and outcome.missed == []


# --- citation-exists ---


def test_corpus_sections_contains_real_sections():
    assert "6-1-1704" in SECTIONS["Colorado"]
    assert "Sec. 9" in SECTIONS["Connecticut"]
    assert "775 ILCS 5/2-102" in SECTIONS["Illinois"]
    assert "6-1-9999" not in SECTIONS["Colorado"]  # not a real section


def _memo(*citations: str) -> ComplianceMemo:
    return ComplianceMemo(
        per_law=[
            LawFinding(
                law_id="co-sb26-189",
                short_name="CO SB 26-189",
                in_scope="yes",
                why="test",
                obligations=[MemoObligation(text="t", citation=c) for c in citations],
            )
        ],
        disclaimer="d",
    )


def test_citation_exists_passes_real_flags_fake():
    out = score_citation_exists(_memo("Colorado § 6-1-1704", "Colorado § 6-1-9999"), SECTIONS)
    assert out.total == 2
    assert out.valid == 1
    assert out.invalid == ["Colorado § 6-1-9999"]


def test_citation_exists_flags_cross_jurisdiction():
    # A real Colorado section number, but cited as a Connecticut section -> not real for CT.
    out = score_citation_exists(_memo("Connecticut § 6-1-1704"), SECTIONS)
    assert out.invalid == ["Connecticut § 6-1-1704"]


def test_citation_exists_section_boundary():
    # "Sec. 99" must not match the real "Sec. 9" via substring.
    out = score_citation_exists(_memo("Connecticut Sec. 99"), SECTIONS)
    assert out.invalid == ["Connecticut Sec. 99"]
    # but the real "Sec. 10" resolves.
    assert score_citation_exists(_memo("Connecticut Sec. 10"), SECTIONS).valid == 1


def test_locate_section_resolves_guards_and_boundary():
    assert locate_section("Colorado § 6-1-1704", SECTIONS) == ("Colorado", "6-1-1704")
    assert locate_section("Connecticut § 6-1-1704", SECTIONS) is None  # cross-jurisdiction
    assert locate_section("Connecticut Sec. 99", SECTIONS) is None  # boundary guard
    assert locate_section("Connecticut Sec. 10", SECTIONS) == ("Connecticut", "Sec. 10")
    assert locate_section("Illinois 775 ILCS 5/2-102(L)(1)", SECTIONS) == (
        "Illinois",
        "775 ILCS 5/2-102",
    )
    assert locate_section("775 ILCS 5/2-999", SECTIONS) is None  # not a real IL section


# --- coverage (fuzzy, free) ---


def test_coverage_matches_paraphrase_and_flags_missing():
    memo = ComplianceMemo(
        per_law=[
            LawFinding(
                law_id="co-sb26-189",
                short_name="CO",
                in_scope="yes",
                why="t",
                obligations=[
                    MemoObligation(text="Provide a point-of-interaction notice", citation="x")
                ],
            )
        ],
        disclaimer="d",
    )
    out = score_coverage(memo, ["Provide a point-of-interaction notice", "Totally unrelated duty"])
    assert out.total == 2
    assert out.covered == 1
    assert out.missed == ["Totally unrelated duty"]


# --- judge tier (stubbed judge, no API calls) ---


class _StubJudge:
    """Stands in for the Opus judge: returns a fixed verdict for any call (no network)."""

    def __init__(self, verdict: JudgeVerdict):
        self._verdict = verdict

    def complete_structured(self, system, messages, schema):
        return self._verdict


def test_judge_verdict_schema():
    v = JudgeVerdict(grounded="partial", reason="overstated")
    assert v.grounded == "partial"
    assert v.unsupported_claims == []


def test_groundedness_aggregates_verdicts():
    memo = _memo("Colorado § 6-1-1704")
    texts = {"Colorado": {"6-1-1704": "notice text"}}
    yes = score_groundedness(memo, texts, _StubJudge(JudgeVerdict(grounded="yes", reason="ok")))
    assert (yes.judged, yes.grounded_yes) == (1, 1)
    no = score_groundedness(
        memo, texts, _StubJudge(JudgeVerdict(grounded="no", reason="x", unsupported_claims=["foo"]))
    )
    assert no.grounded_yes == 0
    assert no.unsupported == ["foo"]


def test_groundedness_skips_unlocatable_citation():
    memo = _memo("Colorado § 6-1-9999")  # not a real section -> nothing to judge against
    out = score_groundedness(
        memo, {"Colorado": {"6-1-1704": "t"}}, _StubJudge(JudgeVerdict(grounded="yes", reason=""))
    )
    assert out.judged == 0


# --- spending guardrails ---


class _FakeStdin:
    def __init__(self, tty: bool):
        self._tty = tty

    def isatty(self) -> bool:
        return self._tty


def test_confirm_spend_blocks_over_cap():
    # Hard cap is checked first, before any terminal/confirmation — a runaway can't even prompt.
    assert confirm_spend(description="x", units=100, cap=50) is False


def test_confirm_spend_refuses_non_interactive(monkeypatch):
    monkeypatch.setattr("sys.stdin", _FakeStdin(tty=False))
    assert confirm_spend(description="x", units=1, cap=50) is False


def test_confirm_spend_requires_typed_yes(monkeypatch):
    monkeypatch.setattr("sys.stdin", _FakeStdin(tty=True))
    monkeypatch.setattr("builtins.input", lambda *_: "yes")
    assert confirm_spend(description="x", units=1, cap=50, est_cost_usd=0.1) is True
    monkeypatch.setattr("builtins.input", lambda *_: "nope")
    assert confirm_spend(description="x", units=1, cap=50) is False


def test_judged_dump_routes_through_shared_renderer():
    """Phase 11 §8: the judged-tier HTML dump body goes through core.render.memo_to_html (one shared
    layout, no second template to drift), with only the eval-specific scores banner + raw-JSON wrapper
    added around it."""
    from types import SimpleNamespace

    from eval.run import _memo_to_html

    memo = ComplianceMemo(
        per_law=[
            LawFinding(
                law_id="co",
                short_name="CO SB 26-189",
                in_scope="yes",
                why="Likely applies.",
                obligations=[
                    MemoObligation(text="Provide notice.", citation="Colorado § 6-1-1704")
                ],
            )
        ],
        disclaimer="Educational analysis, not legal advice.",
    )
    cite = SimpleNamespace(valid=2, total=2, invalid=0)
    grounded = SimpleNamespace(grounded_yes=3, judged=3)
    coverage = SimpleNamespace(covered=1, total=1, missed=0)
    out = _memo_to_html(memo, "co/basic", cite, grounded, coverage)

    # Distinctive renderer markup proves the body routed through the shared helper.
    assert "PATCHWORK ASSURANCE" in out
    assert "Educational Compliance Memorandum" in out
    assert "Colorado § 6-1-1704" in out
    # Eval-only wrapper present.
    assert "eval co/basic" in out
    assert "citations real 2/2" in out
    assert "raw memo JSON" in out
