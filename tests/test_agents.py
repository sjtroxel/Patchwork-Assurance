"""Phase 12 multi-agent pipeline — offline, StubLLM, zero spend."""

from datetime import date

from patchwork_assurance.core.agents.analyst import analyze_law
from patchwork_assurance.core.agents.trace import AgentTrace
from patchwork_assurance.core.contracts import (
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


CO_SCOPE = ScopeResult(
    law_id="co-sb-26-189",
    short_name="CO AI Act",
    jurisdiction="CO",
    in_scope="yes",
    reason="CO nexus + deployer + employment.",
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
