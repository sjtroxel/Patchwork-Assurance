"""Memo generation tests — offline, StubLLM, no API key."""

from datetime import date

from patchwork_assurance.core.contracts import (
    ComplianceMemo,
    LawFinding,
    MemoObligation,
    RetrievedChunk,
    ScopeResult,
    Situation,
)
from patchwork_assurance.core.corpus.metadata import EffectiveDate, LawMetadata
from patchwork_assurance.core.llm import StubLLM
from patchwork_assurance.core.memo import generate_memo
from patchwork_assurance.core.prompts import DISCLAIMER

# ---- stub helpers ----


class _StubRetriever:
    def __init__(self, chunks):
        self._chunks = chunks

    def retrieve(self, query, filters=None, k=5):
        return self._chunks[:k]


CHUNK = RetrievedChunk(
    text="Deployers must provide notice.",
    citation="CO SB 26-189 § 6-1-1703(1)",
    section_number="6-1-1703",
    section_heading="Deployer duties",
    jurisdiction="CO",
    law_id="co-sb-26-189",
    score=0.9,
)

CANNED_MEMO = ComplianceMemo(
    per_law=[
        LawFinding(
            law_id="co-sb-26-189",
            short_name="CO AI Act",
            in_scope="yes",
            why="Nexus + deployer + employment.",
            obligations=[
                MemoObligation(text="Provide notice.", citation="CO SB 26-189 § 6-1-1703(1)")
            ],
            effective_dates=["2026-02-01"],
        )
    ],
    disclaimer=DISCLAIMER,
)

SCOPE = [
    ScopeResult(
        law_id="co-sb-26-189",
        short_name="CO AI Act",
        jurisdiction="CO",
        in_scope="yes",
        reason="Nexus + deployer + employment.",
    ),
    ScopeResult(
        law_id="ct-sb-5",
        short_name="CT AI Act",
        jurisdiction="CT",
        in_scope="no",
        reason="No CT nexus.",
    ),
]

SITUATION = Situation(jurisdictions=["CO"], decision_domains=["employment"], roles=["deployer"])


def test_generate_memo_returns_compliance_memo():
    llm = StubLLM(structured=CANNED_MEMO)
    retriever = _StubRetriever([CHUNK])
    memo = generate_memo(SITUATION, SCOPE, retriever, llm)
    assert isinstance(memo, ComplianceMemo)


def test_memo_has_disclaimer():
    llm = StubLLM(structured=CANNED_MEMO)
    retriever = _StubRetriever([CHUNK])
    memo = generate_memo(SITUATION, SCOPE, retriever, llm)
    assert memo.disclaimer == DISCLAIMER


def test_memo_per_law_shape():
    llm = StubLLM(structured=CANNED_MEMO)
    retriever = _StubRetriever([CHUNK])
    memo = generate_memo(SITUATION, SCOPE, retriever, llm)
    assert len(memo.per_law) == 1
    assert memo.per_law[0].law_id == "co-sb-26-189"


def test_retriever_only_called_for_in_scope_laws():
    """Retriever should only be called for laws that are in_scope in ('yes', 'uncertain')."""
    calls = []

    class _TrackingRetriever:
        def retrieve(self, query, filters=None, k=5):
            calls.append(filters.law_id if filters else None)
            return []

    llm = StubLLM(structured=CANNED_MEMO)
    generate_memo(SITUATION, SCOPE, _TrackingRetriever(), llm)
    # CO is in_scope=yes → called; CT is in_scope=no → not called. Filter is per law_id, not
    # jurisdiction (a jurisdiction can hold more than one law, e.g. California).
    assert "co-sb-26-189" in calls
    assert "ct-sb-5" not in calls


def test_memo_out_of_scope_all_no():
    """When all laws are out of scope, retriever is never called and the stub still returns a memo."""
    all_no_scope = [
        ScopeResult(
            law_id="co-sb-26-189",
            short_name="CO AI Act",
            jurisdiction="CO",
            in_scope="no",
            reason="No nexus.",
        ),
        ScopeResult(
            law_id="ct-sb-5",
            short_name="CT AI Act",
            jurisdiction="CT",
            in_scope="no",
            reason="No nexus.",
        ),
    ]
    calls = []

    class _TrackingRetriever:
        def retrieve(self, query, filters=None, k=5):
            calls.append(True)
            return []

    llm = StubLLM(structured=CANNED_MEMO)
    memo = generate_memo(SITUATION, all_no_scope, _TrackingRetriever(), llm)
    assert isinstance(memo, ComplianceMemo)
    assert calls == []


# ---- Phase 4.6: deterministic deadlines + templated next steps ----


def _ct_law():
    return LawMetadata.model_construct(
        law_id="ct-sb-5",
        short_name="CT AI Act",
        jurisdiction="CT",
        operative_standard="AERDT = substantial factor in an employment-related decision",
        regulated_roles=["developer", "deployer"],
        scope_domains=["employment", "ai_companion"],
        enforcement_authority="Connecticut Attorney General",
        key_obligations=[],
        effective_dates=[
            EffectiveDate(
                date=date(2027, 10, 1), applies_to="deployer pre-decision written notice"
            ),
            EffectiveDate(date=date(2026, 10, 1), applies_to="employment provisions"),
        ],
    )


CT_IN_SCOPE = [
    ScopeResult(
        law_id="ct-sb-5",
        short_name="CT AI Act",
        jurisdiction="CT",
        in_scope="yes",
        reason="CT nexus.",
    )
]
CT_SITUATION = Situation(jurisdictions=["CT"], decision_domains=["employment"], roles=["deployer"])


def test_memo_stamps_generated_on_and_corpus_as_of():
    """Phase 11: generated_on is today (stamped at generation, not the LLM); corpus_as_of is the
    LATEST retrieved_on across the laws considered — the trustworthy 'as of' date for the PDF."""

    def _law(law_id, short_name, jur, retrieved):
        return LawMetadata.model_construct(
            law_id=law_id,
            short_name=short_name,
            jurisdiction=jur,
            operative_standard="",
            regulated_roles=["deployer"],
            scope_domains=["employment"],
            enforcement_authority="",
            key_obligations=[],
            effective_dates=[],
            retrieved_on=retrieved,
        )

    law_co = _law("co-sb-26-189", "CO AI Act", "CO", date(2026, 6, 17))
    law_ct = _law("ct-sb-5", "CT AI Act", "CT", date(2026, 6, 27))
    memo = generate_memo(
        SITUATION,
        SCOPE,
        _StubRetriever([CHUNK]),
        StubLLM(structured=CANNED_MEMO),
        [law_co, law_ct],
    )
    assert memo.generated_on == date.today().isoformat()
    assert memo.corpus_as_of == "2026-06-27"  # max(retrieved_on), not the CO date


def test_memo_stamps_without_law_metadata():
    """generated_on is always stamped; corpus_as_of is None when no law metadata is supplied."""
    memo = generate_memo(
        SITUATION, SCOPE, _StubRetriever([CHUNK]), StubLLM(structured=CANNED_MEMO), []
    )
    assert memo.generated_on == date.today().isoformat()
    assert memo.corpus_as_of is None


def test_deadlines_are_deterministic_and_sorted():
    memo = generate_memo(
        CT_SITUATION,
        CT_IN_SCOPE,
        _StubRetriever([CHUNK]),
        StubLLM(structured=CANNED_MEMO),
        [_ct_law()],
    )
    dates = [d.date for d in memo.deadline_checklist]
    assert "2027-10-01" in dates  # the AERDT deployer-notice date surfaces
    assert dates == sorted(dates)  # staggered dates in order, not collapsed


def test_next_steps_inventory_when_unsure():
    sit = Situation(
        jurisdictions=["CO"], decision_domains=["employment"], roles=["deployer"], ai_use="unsure"
    )
    memo = generate_memo(sit, SCOPE, _StubRetriever([CHUNK]), StubLLM(structured=CANNED_MEMO), [])
    assert any("inventory" in s.lower() for s in memo.next_steps)
    assert any("licensed attorney" in s.lower() for s in memo.next_steps)


def test_next_steps_flags_ct_broader_scope():
    memo = generate_memo(
        CT_SITUATION,
        CT_IN_SCOPE,
        _StubRetriever([CHUNK]),
        StubLLM(structured=CANNED_MEMO),
        [_ct_law()],
    )
    assert any("ai companion" in s.lower() for s in memo.next_steps)


def test_next_steps_out_of_scope_single_message():
    all_no = [
        ScopeResult(
            law_id="co-sb-26-189",
            short_name="CO AI Act",
            jurisdiction="CO",
            in_scope="no",
            reason="x",
        )
    ]
    memo = generate_memo(
        SITUATION, all_no, _StubRetriever([CHUNK]), StubLLM(structured=CANNED_MEMO), []
    )
    assert len(memo.next_steps) == 1
    assert "appears to reach you" in memo.next_steps[0].lower()
