"""Tests for the Phase 14 prose renderer (eval/prose.py).

The renderer is the measurement instrument for the benchmark: it is the seam where the experiment
could be rigged in either direction. These tests pin the three rules from phase-14 IMPLEMENTATION §5
— deterministic, lossless, neutral — rather than the exact wording, which is meant to stay editable
after the read-by-eye review.
"""

import pytest
from eval.loader import load_gold
from eval.prose import _DOMAIN_PROSE, render_situation_prose

from patchwork_assurance.core.contracts import Situation

# The 13-case Phase 14 set (IMPLEMENTATION §3.1).
PHASE_14_CASE_IDS = [
    "co-employment-deployer",
    "co-cpa-lending-deployer",
    "ct-employment-deployer",
    "ct-ctdpa-lending-deployer",
    "il-employment-deployer",
    "il-aivia-video-interview",
    "nj-employment-deployer",
    "nj-njdpa-insurance-deployer",
    "ca-employment-deployer",
    "ca-ccpa-housing-deployer",
    "tx-employment-deployer",
    "tx-co-multistate",
    "no-regulating-nexus",
]

# Operative terms and legal vocabulary that must never appear in rendered prose. Writing any of these
# hands the model the finding it is supposed to reach on its own. Drawn from the corpus's
# do-not-harmonize list (CLAUDE.md) plus the role taxonomy.
_LEAKY_TERMS = [
    "materially influence",  # Colorado SB 26-189 (ADMT)
    "substantial factor",  # Connecticut SB 5 (AERDT)
    "consequential decision",  # CO/CT trigger
    "disparate impact",  # NJ 13:16 / IL HB 3773
    "algorithmic discrimination",
    "automated decision",
    "profiling",  # the privacy-law cluster's operative term
    "deployer",
    "developer",
    "aedt",
    "admt",
    "bias audit",
    "impact assessment",
]


def _gold_by_id() -> dict[str, object]:
    return {c.id: c for c in load_gold()}


@pytest.fixture(scope="module")
def gold():
    return _gold_by_id()


def test_deterministic_across_calls():
    s = Situation(
        jurisdictions=["Colorado"],
        decision_domains=["employment"],
        roles=["deployer"],
        ai_use="yes",
    )
    assert render_situation_prose(s) == render_situation_prose(s)


@pytest.mark.parametrize("case_id", PHASE_14_CASE_IDS)
def test_lossless_over_the_phase_14_set(gold, case_id):
    """Every field carrying a value is represented in the prose."""
    situation = gold[case_id].situation
    prose = render_situation_prose(situation)

    if situation.home_state:
        assert situation.home_state in prose, f"{case_id}: home_state dropped"
    for jurisdiction in situation.jurisdictions:
        assert jurisdiction in prose, f"{case_id}: jurisdiction {jurisdiction} dropped"
    for domain in situation.decision_domains:
        assert _DOMAIN_PROSE[domain] in prose, f"{case_id}: domain {domain} dropped"
    if situation.notes:
        assert situation.notes in prose, f"{case_id}: notes dropped"
    # Role is rendered as a described fact rather than the taxonomy word, so assert on the gloss.
    if situation.roles:
        assert "build" in prose, f"{case_id}: role not conveyed"


@pytest.mark.parametrize("case_id", PHASE_14_CASE_IDS)
def test_neutral_no_leaky_legal_vocabulary(gold, case_id):
    """The prose must not hand over an operative term or the role taxonomy."""
    prose = render_situation_prose(gold[case_id].situation).lower()
    for term in _LEAKY_TERMS:
        assert term not in prose, f"{case_id}: leaked operative term {term!r}"


@pytest.mark.parametrize("case_id", PHASE_14_CASE_IDS)
def test_no_law_names_or_citations_leak(gold, case_id):
    """No statute, bill number, or jurisdiction-specific law name in the prose."""
    prose = render_situation_prose(gold[case_id].situation).lower()
    for token in ["sb ", "hb ", "ilcs", "n.j.a.c", "ccpa", "cpa", "traiga", "feha", "aivia", "§"]:
        assert token not in prose, f"{case_id}: leaked law reference {token!r}"


def test_ai_use_no_is_rendered_as_an_exclusion():
    s = Situation(jurisdictions=["Colorado"], decision_domains=["employment"], ai_use="no")
    assert "do not use AI" in render_situation_prose(s)


def test_ai_use_unsure_is_rendered_as_uncertainty_not_a_yes():
    s = Situation(jurisdictions=["Colorado"], decision_domains=["employment"], ai_use="unsure")
    prose = render_situation_prose(s)
    assert "not sure" in prose
    assert "We use AI to help make" not in prose


def test_blank_fields_render_nothing_rather_than_a_guess():
    """A user who did not say is rendered as silence. The absence is the signal."""
    prose = render_situation_prose(Situation(ai_use="yes"))
    assert "based in" not in prose
    assert "The people these decisions affect are in" not in prose
    assert "build" not in prose


def test_both_roles_renders_as_both():
    s = Situation(
        jurisdictions=["Colorado"], decision_domains=["employment"], roles=["deployer", "developer"]
    )
    prose = render_situation_prose(s)
    assert "provide them to other businesses" in prose
    assert "use them ourselves" in prose


def test_multistate_joins_jurisdictions():
    s = Situation(jurisdictions=["Texas", "Colorado"], decision_domains=["employment"])
    assert "Texas and Colorado" in render_situation_prose(s)


def test_every_corpus_domain_has_a_prose_gloss():
    """Guards the corpus seam: a new ScopeDomain must get a gloss, not silently vanish."""
    from typing import get_args

    from patchwork_assurance.core.corpus.metadata import ScopeDomain

    for domain in get_args(ScopeDomain):
        assert domain in _DOMAIN_PROSE, f"domain {domain!r} has no prose gloss"


def test_aivia_case_is_distinguishable_from_the_hb3773_case(gold):
    """The AIVIA collision, fixed 2026-07-16 (found at step 1's read-by-eye gate).

    The two Illinois cases had byte-identical `situation` objects — the video-interview fact lived
    only in the `rationale`, which is documentation, not input. Both therefore rendered to the same
    prose, so no arm could pass both, and §3.1's do-not-harmonize probe for the AIVIA case measured
    nothing: a model never told about video interviews that misses AIVIA has not harmonized anything.

    Fixed by adding the fact to `situation.notes` (ignored by the gate and by retrieval; reaches the
    memo prompt only, symmetrically for every arm). This test pins the property that actually matters
    — the two cases must present differently — rather than the wording.
    """
    aivia = render_situation_prose(gold["il-aivia-video-interview"].situation)
    hb3773 = render_situation_prose(gold["il-employment-deployer"].situation)
    assert aivia != hb3773, "the two Illinois cases render identically — the AIVIA probe is dead"
    assert "video" in aivia.lower(), "the video-interview fact did not reach the prose"
    assert "video" not in hb3773.lower(), "the HB 3773 case should not mention video"


def test_aivia_notes_state_the_fact_without_leaking_the_rule(gold):
    """The notes must not hand over the obligations the model is supposed to reach on its own."""
    prose = render_situation_prose(gold["il-aivia-video-interview"].situation).lower()
    for rule_word in ["consent", "notify", "notice", "retention", "delete", "30 days"]:
        assert rule_word not in prose, f"AIVIA notes leaked the rule: {rule_word!r}"
