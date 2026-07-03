"""Memo generation tests — offline, StubLLM, no API key."""

from datetime import date

import pytest

from patchwork_assurance.config import Settings
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


@pytest.fixture(autouse=True)
def _pin_single_pipeline(monkeypatch):
    # The product default is now multi_agent (Phase 12 eval cleared it, 2026-07-02). The tests in this
    # module exercise the single-call generation path + the shared deterministic overlays (identical in
    # both pipelines), so pin single here. The multi_agent dispatch test overrides this in its own body.
    monkeypatch.setattr("patchwork_assurance.core.memo.settings.memo_pipeline", "single")


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


# ---- Phase 12: generate_memo dispatch on the memo_pipeline flag ----


def test_product_default_pipeline_is_multi_agent():
    # The shipped default (Phase 12 eval, 2026-07-02) is multi_agent. Assert the config field default
    # directly (immune to env/.env overrides and to the autouse single pin) so a flip-back can't slip
    # through unnoticed.
    assert Settings.model_fields["memo_pipeline"].default == "multi_agent"


def test_single_pipeline_generates(monkeypatch):
    # The one-call path still runs and returns a full memo when single is selected.
    monkeypatch.setattr("patchwork_assurance.core.memo.settings.memo_pipeline", "single")
    memo = generate_memo(SITUATION, SCOPE, _StubRetriever([CHUNK]), StubLLM(structured=CANNED_MEMO))
    assert isinstance(memo, ComplianceMemo)


def test_multi_agent_pipeline_runs_end_to_end(monkeypatch):
    # Flip the flag: generate_memo now runs the real analyst->reviewer pipeline offline on a bare stub
    # (analyst + the internally-built reviewer are both StubLLM; section_texts read from the real
    # corpus on disk). Returns a valid, overlay-stamped ComplianceMemo — no NotImplementedError.
    # Force the STUB provider: the multi_agent path builds its reviewer via build_llm(settings, ...),
    # which would otherwise honor a real LLM_PROVIDER in .env and hit the network. Offline discipline.
    monkeypatch.setattr("patchwork_assurance.core.memo.settings.memo_pipeline", "multi_agent")
    monkeypatch.setattr("patchwork_assurance.core.memo.settings.llm_provider", "stub")
    law = LawMetadata.model_construct(
        law_id="co-sb-26-189",
        short_name="CO AI Act",
        jurisdiction="CO",
        operative_standard="",
        regulated_roles=["deployer"],
        scope_domains=["employment"],
        enforcement_authority="",
        key_obligations=[],
        effective_dates=[],
    )
    memo = generate_memo(SITUATION, SCOPE, _StubRetriever([CHUNK]), StubLLM(), [law])
    assert isinstance(memo, ComplianceMemo)
    assert memo.disclaimer == DISCLAIMER  # assembly sets the chrome
    assert memo.generated_on == date.today().isoformat()  # deterministic overlay still applied
    assert [f.law_id for f in memo.per_law] == ["co-sb-26-189"]  # only the in-scope law


def test_retrieve_per_law_pins_key_obligation_sections():
    """A law's curated key-obligation section that semantic top-k ranks past the k-window is still
    grounded: retrieve_per_law refetches it by section. Regression lock for the TRAIGA gap found
    2026-07-03 (§ 552.056, the one private-employer rule, ranked ~19th under a generic focus query
    and never made k=8, so the memo grounded in sandbox/council sections instead)."""
    from patchwork_assurance.core.corpus.metadata import LawMetadata, Obligation
    from patchwork_assurance.core.memo import retrieve_per_law

    distractor = RetrievedChunk(
        text="regulatory sandbox program",
        citation="Tex. Bus. & Com. Code § 553.054",
        section_number="553.054",
        section_heading="Efficient Use of Resources",
        jurisdiction="Texas",
        law_id="tx-traiga",
        score=0.9,
        chunk_index=23,
    )
    material = RetrievedChunk(
        text="may not deploy AI with intent to unlawfully discriminate",
        citation="Tex. Bus. & Com. Code § 552.056",
        section_number="552.056",
        section_heading="Unlawful Discrimination",
        jurisdiction="Texas",
        law_id="tx-traiga",
        score=0.4,
        chunk_index=11,
    )

    class _PinAwareRetriever:
        """Semantic top-k returns only the distractor (mirrors 552.056 ranking out of the window);
        the section-scoped refetch is the only way to surface the material section."""

        def retrieve(self, query, filters=None, k=5):
            if filters and filters.section_number == "552.056":
                return [material]
            if filters and filters.section_number:
                return []  # other key-obligation sections not modeled in this stub
            return [distractor]

    law = LawMetadata.model_construct(
        law_id="tx-traiga",
        key_obligations=[
            Obligation(section="Tex. Bus. & Com. Code § 552.056", label="Unlawful discrimination")
        ],
    )
    scope = [
        ScopeResult(
            law_id="tx-traiga",
            short_name="TX TRAIGA",
            jurisdiction="Texas",
            in_scope="yes",
            reason="",
        )
    ]
    buckets = retrieve_per_law(SITUATION, scope, _PinAwareRetriever(), {"tx-traiga": law})
    got = {c.section_number for c in buckets["tx-traiga"]}
    assert "552.056" in got  # pinned in despite being missed by semantic top-k
    assert "553.054" in got  # the semantic hit is preserved, not replaced
