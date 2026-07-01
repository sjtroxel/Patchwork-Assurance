"""Phase 12 multi-agent pipeline — offline, StubLLM, zero spend."""

import threading
from datetime import date

from patchwork_assurance.core import obs
from patchwork_assurance.core.agents.analyst import analyze_law
from patchwork_assurance.core.agents.orchestrator import run_analysts, run_multi_agent_memo
from patchwork_assurance.core.agents.reviewer import review_findings
from patchwork_assurance.core.agents.trace import AgentTrace
from patchwork_assurance.core.contracts import (
    ComplianceMemo,
    LawFinding,
    MemoObligation,
    Msg,
    RetrievedChunk,
    ScopeResult,
    Situation,
)
from patchwork_assurance.core.corpus.metadata import EffectiveDate, LawMetadata
from patchwork_assurance.core.judge import JudgeVerdict
from patchwork_assurance.core.llm import StubLLM
from patchwork_assurance.core.prompts import DISCLAIMER

# ---- fixtures ----

CO_CHUNK = RetrievedChunk(
    text="A deployer shall provide the consumer notice that ADMT is in use.",
    citation="Colo. Rev. Stat. §§ 6-1-1701 to 6-1-1709",
    section_number="6-1-1704",
    section_heading="Deployer notice",
    jurisdiction="Colorado",
    law_id="co-sb-26-189",
    score=0.9,
)
# A token that appears ONLY in CT's text, so we can prove it never leaks into a CO analyst prompt.
CT_LEAK_TOKEN = "ctsubstantialfactorleaktoken"
CT_CHUNK = RetrievedChunk(
    text=f"An AERDT that is a {CT_LEAK_TOKEN} in an employment decision.",
    citation="Conn. SB 5",
    section_number="Sec. 4",
    section_heading="AERDT",
    jurisdiction="Connecticut",
    law_id="ct-sb-5",
    score=0.9,
)


def _co_law():
    return LawMetadata.model_construct(
        law_id="co-sb-26-189",
        short_name="CO AI Act",
        jurisdiction="CO",
        operative_standard="ADMT = materially influence a consequential decision",
        regulated_roles=["deployer"],
        scope_domains=["employment"],
        enforcement_authority="Colorado Attorney General",
        key_obligations=[],
        effective_dates=[EffectiveDate(date=date(2027, 1, 1), applies_to="all provisions")],
    )


def _ct_law():
    return LawMetadata.model_construct(
        law_id="ct-sb-5",
        short_name="CT AI Act",
        jurisdiction="CT",
        operative_standard="AERDT = substantial factor in an employment decision",
        regulated_roles=["deployer"],
        scope_domains=["employment"],
        enforcement_authority="Connecticut Attorney General",
        key_obligations=[],
        effective_dates=[EffectiveDate(date=date(2026, 10, 1), applies_to="employment provisions")],
    )


CO_SCOPE = ScopeResult(
    law_id="co-sb-26-189",
    short_name="CO AI Act",
    jurisdiction="CO",
    in_scope="yes",
    reason="CO nexus + deployer + employment.",
)
CT_SCOPE = ScopeResult(
    law_id="ct-sb-5",
    short_name="CT AI Act",
    jurisdiction="CT",
    in_scope="yes",
    reason="CT nexus.",
)
SIT = Situation(jurisdictions=["CO"], decision_domains=["employment"], roles=["deployer"])

# The model's raw output carries wrong identity fields on purpose — analyze_law must overwrite them.
RAW_FINDING = LawFinding(
    law_id="model-guessed-wrong",
    short_name="Model Guess",
    in_scope="no",
    why="Likely applies: deployer using ADMT in employment.",
    obligations=[MemoObligation(text="Provide consumer notice.", citation="Colorado § 6-1-1704")],
    effective_dates=["9999-01-01"],
)


class _SpyLLM:
    """Captures the user prompt so we can assert isolation; returns a fresh copy each call."""

    def __init__(self, finding: LawFinding):
        self._finding = finding
        self.captured = ""

    def complete_structured(self, system, messages, schema, max_tokens=16000):
        self.captured = messages[0].content
        return self._finding.model_copy(deep=True)


# ---- StubLLM extension (step 3) ----


def test_stub_structured_by_schema_drains_queue():
    f1 = RAW_FINDING.model_copy(update={"why": "first"})
    f2 = RAW_FINDING.model_copy(update={"why": "second"})
    llm = StubLLM(structured_by_schema={LawFinding: [f1, f2]})
    a = llm.complete_structured("s", [Msg(role="user", content="x")], LawFinding)
    b = llm.complete_structured("s", [Msg(role="user", content="x")], LawFinding)
    assert (a.why, b.why) == ("first", "second")  # FIFO per call


def test_stub_structured_by_schema_is_keyed_by_schema():
    # A LawFinding queue and a JudgeVerdict fixed value don't consume each other, even interleaved.
    verdict = JudgeVerdict(grounded="yes", reason="ok")
    llm = StubLLM(structured_by_schema={LawFinding: RAW_FINDING, JudgeVerdict: verdict})
    assert isinstance(llm.complete_structured("s", [], JudgeVerdict), JudgeVerdict)
    assert isinstance(llm.complete_structured("s", [], LawFinding), LawFinding)
    assert isinstance(llm.complete_structured("s", [], JudgeVerdict), JudgeVerdict)


# ---- analyst agent (step 4) ----


def test_analyze_law_returns_finding_and_trace():
    llm = StubLLM(structured_by_schema={LawFinding: RAW_FINDING})
    finding, trace = analyze_law(_co_law(), SIT, CO_SCOPE, [CO_CHUNK], llm, "claude-sonnet-5")
    assert isinstance(finding, LawFinding)
    assert isinstance(trace, AgentTrace)
    assert trace.law_id == "co-sb-26-189"
    assert trace.model == "claude-sonnet-5"
    assert trace.status == "ok"


def test_analyze_law_stamps_identity_and_dates_deterministically():
    # The model returned wrong law_id/short_name/in_scope/effective_dates; analyze_law overwrites them
    # from the deterministic scope + metadata (the agent can't move the un-fishable verdict).
    llm = StubLLM(structured_by_schema={LawFinding: RAW_FINDING})
    finding, _ = analyze_law(_co_law(), SIT, CO_SCOPE, [CO_CHUNK], llm, "claude-sonnet-5")
    assert finding.law_id == "co-sb-26-189"
    assert finding.short_name == "CO AI Act"
    assert finding.in_scope == "yes"  # not the model's "no"
    assert finding.effective_dates == ["2027-01-01"]  # from metadata, not the model's "9999-01-01"
    assert finding.why.startswith("Likely applies")  # analysis prose IS the model's


def test_analyst_prompt_isolated_to_its_own_law():
    # Give the CO analyst only CO inputs; its prompt must contain CO's excerpt and NOT any CT text —
    # the structural contamination guard (Phase 12 §4).
    spy = _SpyLLM(RAW_FINDING)
    analyze_law(_co_law(), SIT, CO_SCOPE, [CO_CHUNK], spy, "claude-sonnet-5")
    assert "consumer notice that ADMT is in use" in spy.captured
    assert CT_LEAK_TOKEN not in spy.captured
    assert "CT AI Act" not in spy.captured


# ---- fan-out orchestrator (step 5) ----


def test_run_analysts_generic_over_n_returns_scope_order():
    in_scope = [CO_SCOPE, CT_SCOPE]
    buckets = {"co-sb-26-189": [CO_CHUNK], "ct-sb-5": [CT_CHUNK]}
    laws = {"co-sb-26-189": _co_law(), "ct-sb-5": _ct_law()}
    # Distinct copies so parallel analysts never mutate one shared object (in prod each LLM call
    # returns a fresh object). The queue drains in completion order, but analyze_law re-stamps identity
    # from each law's own scope/metadata, so the result is correct regardless of who finishes first.
    llm = StubLLM(
        structured_by_schema={
            LawFinding: [RAW_FINDING.model_copy(deep=True), RAW_FINDING.model_copy(deep=True)]
        }
    )
    findings, traces = run_analysts(SIT, in_scope, buckets, laws, llm, "claude-sonnet-5")
    # Returned in SCOPE order, not completion order (deterministic assembly downstream).
    assert [f.law_id for f in findings] == ["co-sb-26-189", "ct-sb-5"]
    assert [t.law_id for t in traces] == ["co-sb-26-189", "ct-sb-5"]
    assert all(f.in_scope == "yes" for f in findings)
    # Each finding's dates come from its OWN law's metadata — proof the reorder didn't cross wires.
    assert findings[0].effective_dates == ["2027-01-01"]  # CO
    assert findings[1].effective_dates == ["2026-10-01"]  # CT


def test_run_analysts_propagates_request_id_into_worker_threads():
    # Without copy_context(), worker threads would see the ContextVar default (""). The lock guards the
    # shared list the parallel workers append to (same reason the stub queue needs one).
    seen: list[str] = []
    lock = threading.Lock()

    class _RidLLM:
        def complete_structured(self, system, messages, schema, max_tokens=16000):
            with lock:
                seen.append(obs.get_request_id())
            return RAW_FINDING.model_copy(deep=True)

    in_scope = [CO_SCOPE, CT_SCOPE]
    buckets = {"co-sb-26-189": [CO_CHUNK], "ct-sb-5": [CT_CHUNK]}
    laws = {"co-sb-26-189": _co_law(), "ct-sb-5": _ct_law()}
    token = obs.set_request_id("rid-abc")
    try:
        run_analysts(SIT, in_scope, buckets, laws, _RidLLM(), "m")
    finally:
        obs.reset_request_id(token)
    assert len(seen) == 2
    assert all(rid == "rid-abc" for rid in seen)  # propagated into both worker threads


# ---- reviewer agent (step 6) ----

SECTION_TEXTS = {
    "Colorado": {
        "6-1-1704": (
            "A deployer of a high-risk artificial intelligence system shall provide a consumer a "
            "notice that the system is in use in making a consequential decision."
        )
    }
}
GROUNDED_OB = MemoObligation(
    text="The statute requires a deployer to provide consumers a notice that the system is in use.",
    citation="Colorado § 6-1-1704",
)
FABRICATED_OB = MemoObligation(
    text="A deployer must register the system annually with the state.",
    citation="Colorado § 6-1-9999",  # resolves to no real section
)
OVERCLAIM_OB = MemoObligation(
    text="This guarantees you are compliant once you send the notice.",
    citation="Colorado § 6-1-1704",
)


def _finding(obligations):
    return LawFinding(
        law_id="co-sb-26-189",
        short_name="CO AI Act",
        in_scope="yes",
        why="Likely applies: deployer using ADMT in employment.",
        obligations=obligations,
    )


class _CountingReviewer:
    """Counts groundedness-judge calls, so we can prove the free pre-filter never spends one."""

    def __init__(self):
        self.judge_calls = 0

    def complete_structured(self, system, messages, schema, max_tokens=16000):
        if schema is JudgeVerdict:
            self.judge_calls += 1
            return JudgeVerdict(grounded="yes", reason="")
        return GROUNDED_OB

    def complete(self, system, messages, max_tokens=16000):
        return "This educational summary is hedged."


def test_fabricated_citation_dropped_without_an_llm_call():
    rev = _CountingReviewer()
    reviewed, _, events = review_findings(
        [_finding([FABRICATED_OB])], SIT, SECTION_TEXTS, rev, "claude-opus-4-8"
    )
    assert rev.judge_calls == 0  # dropped for free by the deterministic pre-filter
    assert reviewed[0].obligations == []
    assert any(e.kind == "review_verdict" and "fabricated" in e.detail for e in events)


def test_grounded_obligation_kept():
    llm = StubLLM(
        text="This educational summary is hedged.",
        structured_by_schema={JudgeVerdict: JudgeVerdict(grounded="yes", reason="ok")},
    )
    reviewed, summary, _ = review_findings(
        [_finding([GROUNDED_OB])], SIT, SECTION_TEXTS, llm, "claude-opus-4-8"
    )
    assert len(reviewed[0].obligations) == 1
    assert summary == "This educational summary is hedged."


def test_unsupported_obligation_dropped():
    llm = StubLLM(structured_by_schema={JudgeVerdict: JudgeVerdict(grounded="no", reason="x")})
    reviewed, _, events = review_findings(
        [_finding([GROUNDED_OB])], SIT, SECTION_TEXTS, llm, "claude-opus-4-8", max_revisions=0
    )
    assert reviewed[0].obligations == []
    assert any("unsupported" in e.detail for e in events)


def test_partial_obligation_flagged_but_kept():
    llm = StubLLM(structured_by_schema={JudgeVerdict: JudgeVerdict(grounded="partial", reason="x")})
    reviewed, _, events = review_findings(
        [_finding([GROUNDED_OB])], SIT, SECTION_TEXTS, llm, "claude-opus-4-8", max_revisions=0
    )
    assert len(reviewed[0].obligations) == 1  # kept
    assert any(e.kind == "review_verdict" and "flagged" in e.detail for e in events)


def test_partial_obligation_revised_then_grounded():
    fixed = MemoObligation(
        text="The statute requires the deployer to notify consumers.", citation="x"
    )
    llm = StubLLM(
        structured_by_schema={
            JudgeVerdict: [  # first judge = partial (triggers revise), second = yes
                JudgeVerdict(grounded="partial", reason="overstated"),
                JudgeVerdict(grounded="yes", reason="ok"),
            ],
            MemoObligation: fixed,
        }
    )
    reviewed, _, events = review_findings(
        [_finding([GROUNDED_OB])], SIT, SECTION_TEXTS, llm, "claude-opus-4-8", max_revisions=1
    )
    assert len(reviewed[0].obligations) == 1
    assert reviewed[0].obligations[0].text == fixed.text  # the revised prose
    assert reviewed[0].obligations[0].citation == "Colorado § 6-1-1704"  # citation preserved
    assert any("revised" in e.detail for e in events)


def test_overclaiming_obligation_dropped():
    llm = StubLLM(structured_by_schema={JudgeVerdict: JudgeVerdict(grounded="yes", reason="ok")})
    reviewed, _, events = review_findings(
        [_finding([OVERCLAIM_OB])], SIT, SECTION_TEXTS, llm, "claude-opus-4-8", max_revisions=0
    )
    assert reviewed[0].obligations == []  # dropped for over-claiming language
    assert any("over-claiming" in e.detail for e in events)


def test_summary_falls_back_when_it_trips_the_language_guard():
    llm = StubLLM(
        text="We guarantee you are compliant.",  # prohibited -> summary must fall back to ""
        structured_by_schema={JudgeVerdict: JudgeVerdict(grounded="yes", reason="ok")},
    )
    _, summary, _ = review_findings(
        [_finding([GROUNDED_OB])], SIT, SECTION_TEXTS, llm, "claude-opus-4-8"
    )
    assert summary == ""


# ---- assembly / run_multi_agent_memo (step 7) ----


class _StubRetriever:
    def __init__(self, chunks):
        self._chunks = chunks

    def retrieve(self, query, filters=None, k=5):
        return self._chunks[:k]


def test_run_multi_agent_memo_assembles_reviewed_memo():
    analyst = StubLLM(structured_by_schema={LawFinding: RAW_FINDING.model_copy(deep=True)})
    reviewer = StubLLM(
        text="This educational summary is hedged.",
        structured_by_schema={JudgeVerdict: JudgeVerdict(grounded="yes", reason="ok")},
    )
    memo = run_multi_agent_memo(
        SIT,
        [
            CO_SCOPE,
            CT_SCOPE,
        ],  # only CO/CT below; CT dropped by out-of-scope? both are in_scope here
        _StubRetriever([CO_CHUNK]),
        analyst,
        reviewer,
        [_co_law(), _ct_law()],
        analyst_model="claude-sonnet-5",
        reviewer_model="claude-opus-4-8",
        section_texts=SECTION_TEXTS,
        max_revisions=0,
    )
    assert isinstance(memo, ComplianceMemo)
    assert [f.law_id for f in memo.per_law] == ["co-sb-26-189", "ct-sb-5"]  # scope order
    assert memo.disclaimer == DISCLAIMER
    assert memo.summary == "This educational summary is hedged."  # reviewer's NL summary
    # RAW_FINDING's obligation (Colorado § 6-1-1704) resolves + judges "yes" -> kept.
    assert all(len(f.obligations) == 1 for f in memo.per_law)


def test_run_multi_agent_memo_summary_none_when_guard_trips():
    analyst = StubLLM(structured_by_schema={LawFinding: RAW_FINDING.model_copy(deep=True)})
    reviewer = StubLLM(
        text="We guarantee you are compliant.",  # trips guard -> reviewer returns "" -> memo None
        structured_by_schema={JudgeVerdict: JudgeVerdict(grounded="yes", reason="ok")},
    )
    memo = run_multi_agent_memo(
        SIT,
        [CO_SCOPE],
        _StubRetriever([CO_CHUNK]),
        analyst,
        reviewer,
        [_co_law()],
        analyst_model="claude-sonnet-5",
        reviewer_model="claude-opus-4-8",
        section_texts=SECTION_TEXTS,
        max_revisions=0,
    )
    assert memo.summary is None  # falls back to the deterministic executive_summary at render time
