"""Phase 14 baseline arm — offline, no API key, no embeddings.

Covers the baseline memo producer (the fair-comparison bridge), the frozen prompts' neutrality (they
must not leak Patchwork's answer), and the `--arm` dispatch regression lock: the patchwork arm must
delegate to the exact production entry point with the exact production arguments (§7.1), and the
baseline arms must never touch it.
"""

from pathlib import Path

import pytest
from eval.baseline import (
    BASELINE_OPEN_SYSTEM,
    BASELINE_PRIMED_SYSTEM,
    _primed_law_block,
    produce_baseline_memo,
)
from eval.harness import Core
from eval.loader import load_gold
from eval.run import PHASE14_CASE_IDS, _produce_memo, _select_cases

from patchwork_assurance.core.contracts import (
    ComplianceMemo,
    Situation,
)
from patchwork_assurance.core.llm import StubLLM
from patchwork_assurance.core.prompts import DISCLAIMER
from patchwork_assurance.core.scope import applicable_laws, load_law_metadata

LAWS = load_law_metadata(Path("corpus"))

_SIT = Situation(
    home_state="Missouri",
    jurisdictions=["Colorado"],
    decision_domains=["employment"],
    roles=["deployer"],
    ai_use="yes",
)


def _case(case_id: str):
    return next(c for c in load_gold() if c.id == case_id)


# --- the producer ---


def test_open_arm_returns_valid_memo_with_pinned_disclaimer():
    memo = produce_baseline_memo(_SIT, StubLLM())  # StubLLM's default is a valid ComplianceMemo
    assert isinstance(memo, ComplianceMemo)
    assert memo.disclaimer == DISCLAIMER


def test_disclaimer_is_pinned_even_when_the_model_omits_or_mangles_it():
    # Chrome (invariant #4) is not left to the model: a baseline memo with a wrong disclaimer is
    # overwritten with the canonical text.
    bad = ComplianceMemo(per_law=[], disclaimer="I certify you are fully compliant.")
    memo = produce_baseline_memo(_SIT, StubLLM(structured=bad))
    assert memo.disclaimer == DISCLAIMER


def test_primed_law_block_lists_every_corpus_law():
    block = _primed_law_block(LAWS)
    for law in LAWS:
        assert law.law_id in block
        assert law.short_name in block


# --- prompt neutrality: the frozen prompts must not hand the model the answer ---

# Answer-leaking tokens: each law's operative term, acronym, or bill number. If any appears in a
# baseline prompt, we would be feeding the frontier model the finding we claim it produced itself.
_LEAK_TOKENS = [
    "materially influence",
    "substantial factor",
    "disparate impact",
    "consequential decision",
    "26-189",
    "24-205",
    "hb 3773",
    "hb 149",
    "sb 1295",
    "traiga",
    "aivia",
    "ctdpa",
    "njdpa",
    "ccpa",
    "feha",
    "local law 144",
    "ll 144",
]


@pytest.mark.parametrize("prompt", [BASELINE_OPEN_SYSTEM, BASELINE_PRIMED_SYSTEM])
def test_baseline_prompts_do_not_leak_the_answer(prompt):
    low = prompt.lower()
    for token in _LEAK_TOKENS:
        assert token not in low, f"baseline prompt leaks {token!r}"


def test_open_prompt_reveals_nothing_about_the_corpus():
    # The open arm must not learn the law count or the jurisdiction count — that would be a nudge (§6).
    low = BASELINE_OPEN_SYSTEM.lower()
    assert "12 law" not in low and "7 juris" not in low and "seven juris" not in low


# --- the --arm dispatch regression lock ---


def test_patchwork_arm_delegates_to_generate_memo_with_production_args(monkeypatch):
    """The regression invariant (§7.1): --arm patchwork is byte-identical to today's behaviour. Proven
    by asserting _produce_memo calls the exact production entry point with the exact production
    arguments — same situation, same deterministic scope, same retriever, same laws."""
    core = Core(retriever=object(), laws=LAWS)
    case = _case("co-employment-deployer")
    llm = StubLLM()
    calls = {}

    def _spy(situation, scope, retriever, memo_llm, laws):
        calls["args"] = (situation, scope, retriever, memo_llm, laws)
        return "MEMO_SENTINEL"

    monkeypatch.setattr("eval.run.generate_memo", _spy)
    out = _produce_memo(core, case, "patchwork", llm)

    assert out == "MEMO_SENTINEL"
    situation, scope, retriever, memo_llm, laws = calls["args"]
    assert situation is case.situation
    assert retriever is core.retriever
    assert laws is core.laws
    assert memo_llm is llm
    # The scope handed to generation is the deterministic gate's own output — no deviation.
    assert scope == applicable_laws(case.situation, core.laws)


def test_grounded_single_uses_the_production_path_with_the_single_pipeline(monkeypatch):
    """The D4 ablation must differ from the patchwork arm in ONE way: the single-pass pipeline. It goes
    through the same production entry point with the same gate, retriever, and laws — anything else
    (a second prompt, a hand-rolled producer) would add a variable and make the ablation unreadable."""
    core = Core(retriever=object(), laws=LAWS)
    case = _case("co-employment-deployer")
    llm = StubLLM()
    calls = {}

    def _spy(situation, scope, retriever, memo_llm, laws, **kwargs):
        calls["args"] = (situation, scope, retriever, memo_llm, laws)
        calls["kwargs"] = kwargs
        return "MEMO_SENTINEL"

    monkeypatch.setattr("eval.run.generate_memo", _spy)
    out = _produce_memo(core, case, "grounded-single", llm)

    assert out == "MEMO_SENTINEL"
    situation, scope, retriever, memo_llm, laws = calls["args"]
    assert situation is case.situation
    assert retriever is core.retriever
    assert laws is core.laws
    assert memo_llm is llm
    assert scope == applicable_laws(case.situation, core.laws)
    # The one variable, injected per call rather than mutated into global settings.
    assert calls["kwargs"] == {"pipeline": "single"}


def test_generate_memo_pipeline_override_does_not_touch_global_settings():
    """Injecting the pipeline must not leak into the rest of the run — the next arm, and production,
    still read the configured default."""
    from patchwork_assurance.config import settings as live

    before = live.memo_pipeline
    core = Core(retriever=object(), laws=LAWS)
    _produce_memo(core, _case("co-employment-deployer"), "baseline-open", StubLLM())
    assert live.memo_pipeline == before


def test_grounded_single_is_gated_like_patchwork_not_like_a_baseline():
    """Both grounded arms run the deterministic gate, so both skip the all-'no' negative control (there
    is no memo to generate). If they diverged here the D4 pair would be comparing different case sets."""
    core = Core(retriever=None, laws=LAWS)
    cases = load_gold()
    patchwork = _select_cases(cases, core, "patchwork")
    cheap = _select_cases(cases, core, "grounded-single")
    assert [c.id for c in cheap] == [c.id for c in patchwork]
    assert _case("no-regulating-nexus") not in cheap


def test_grounded_arms_share_a_groundedness_denominator():
    """Decision #2 applies the strict denominator to RAW arms. Applying it to grounded-single while
    patchwork kept the skip would handicap the ablation in the very comparison it exists to make."""
    from eval.run import _ARMS, _GATED_ARMS

    assert set(_GATED_ARMS) == {"patchwork", "grounded-single"}
    assert all(arm in _ARMS for arm in _GATED_ARMS)
    raw = [a for a in _ARMS if a not in _GATED_ARMS]
    assert raw == ["baseline-open", "baseline-primed"]


def test_baseline_arms_never_call_generate_memo(monkeypatch):
    core = Core(retriever=object(), laws=LAWS)
    case = _case("co-employment-deployer")

    def _boom(*a, **k):
        raise AssertionError("baseline arm must not call generate_memo")

    monkeypatch.setattr("eval.run.generate_memo", _boom)
    # Both baseline arms produce a memo purely from the raw model; primed passes the corpus scope.
    open_memo = _produce_memo(core, case, "baseline-open", StubLLM())
    primed_memo = _produce_memo(core, case, "baseline-primed", StubLLM())
    assert isinstance(open_memo, ComplianceMemo)
    assert isinstance(primed_memo, ComplianceMemo)


# --- arm-aware case selection ---


def test_select_cases_drops_negative_control_for_patchwork_but_not_baselines():
    core = Core(retriever=None, laws=LAWS)  # applicable_laws needs no retriever
    cases = load_gold()
    neg = _case("no-regulating-nexus")
    assert neg not in _select_cases(cases, core, "patchwork")  # nothing applies -> no memo
    assert neg in _select_cases(cases, core, "baseline-open")  # over-claim probe -> must run
    assert neg in _select_cases(cases, core, "baseline-primed")


# --- the frozen publish set ---


def test_phase14_case_set_is_the_thirteen_and_all_exist():
    assert len(PHASE14_CASE_IDS) == 13
    assert len(set(PHASE14_CASE_IDS)) == 13
    known = {c.id for c in load_gold()}
    missing = [cid for cid in PHASE14_CASE_IDS if cid not in known]
    assert not missing, f"phase-14 set names non-existent gold case(s): {missing}"
    assert "no-regulating-nexus" in PHASE14_CASE_IDS  # the negative control is in the set
