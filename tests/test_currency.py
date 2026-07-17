"""Tests for the Phase 14 currency metric (eval/metrics.py score_currency).

Currency is the headline finding (IMPLEMENTATION §5 rank-1, §8), and it is deterministic and free —
which means the only thing standing between it and a wrong headline is these tests.

Two failure directions, both real, both tested:

  A marker that fires on a CORRECT memo  inflates the finding. This is the dangerous one, because
                                         it makes raw models look worse than they are and the
                                         result flatters Patchwork. `test_markers_absent_from_
                                         current_corpus` is the structural guard: a marker must not
                                         appear in the statute as it stands today.
  A marker that never fires              silently deletes the probe. `test_stale_memo_*` pins that
                                         a hand-written superseded memo is actually caught.

The corpus check runs against the real files in `corpus/`, not a fixture, on purpose: the markers
are claims about primary text, and a corpus update must break this test rather than rot the metric.
"""

from pathlib import Path

import pytest
from eval.loader import load_gold
from eval.metrics import _memo_claim_text, _normalize, score_currency

from patchwork_assurance.core.contracts import ComplianceMemo, LawFinding, MemoObligation

CORPUS_DIR = Path(__file__).resolve().parents[1] / "corpus"

# The two currency probes of the 13-case set (IMPLEMENTATION §3.1 cases 1 and 11). Colorado's is the
# repealed-act probe; Texas's is the wrong-version-of-a-live-act probe (§3.2).
CURRENCY_CASE_IDS = ["co-employment-deployer", "tx-employment-deployer"]


@pytest.fixture(scope="module")
def gold():
    return {case.id: case for case in load_gold()}


def _memo(*obligations: str, law_id: str = "co-sb26-189", **kwargs) -> ComplianceMemo:
    """A minimal memo whose obligations carry the given text. Shape only — the metric reads text."""
    return ComplianceMemo(
        per_law=[
            LawFinding(
                law_id=law_id,
                short_name="Test Law",
                in_scope="yes",
                why="test",
                obligations=[MemoObligation(text=t, citation="6-1-1704") for t in obligations],
            )
        ],
        disclaimer="Educational tool, not legal advice.",
        **kwargs,
    )


# --- the structural guard: markers must be absent from the law as it stands today ---


@pytest.mark.parametrize("case_id", CURRENCY_CASE_IDS)
def test_markers_absent_from_current_corpus(gold, case_id):
    """Every stale marker must NOT appear in the current text of any law in scope for that case.

    This is the bar a currency marker has to clear. A phrase that survives into the enacted law
    fires on a correct memo and points the headline metric the wrong way. This test is how
    "disparate impact" and "reasonable care" were rejected as TX markers before they could do
    damage: both appear in enacted TRAIGA, the first inside § 552.056(c) — the clause that states
    the correct answer.
    """
    case = gold[case_id]
    assert case.currency_markers is not None, (
        f"{case_id} is a currency probe and must carry markers"
    )

    in_scope_laws = [law_id for law_id, verdict in case.expect.scope.items() if verdict == "yes"]
    assert in_scope_laws, f"{case_id} has no in-scope law to check markers against"

    for law_id in in_scope_laws:
        text = _normalize((CORPUS_DIR / f"{law_id}.md").read_text())
        for marker in case.currency_markers.stale:
            assert _normalize(marker) not in text, (
                f"{case_id}: stale marker {marker!r} appears in the CURRENT text of {law_id}. "
                f"It would fire on a correct memo. Pick a phrase the enacted law does not use."
            )
        if case.currency_markers.stale_effective_date:
            assert _normalize(case.currency_markers.stale_effective_date) not in text, (
                f"{case_id}: stale_effective_date appears in the current text of {law_id}"
            )


@pytest.mark.parametrize("case_id", CURRENCY_CASE_IDS)
def test_currency_probes_carry_markers(gold, case_id):
    """Both probes are instrumented. The 12-case set shipped TX uninstrumented (§3.2) — the reason
    the set is 13. This test is what keeps that from silently regressing."""
    assert gold[case_id].currency_markers is not None
    assert gold[case_id].currency_markers.stale


def test_only_currency_cases_carry_markers(gold):
    """Markers are additive: the other 42 cases are untouched and score None, not zero."""
    marked = {case_id for case_id, case in gold.items() if case.currency_markers is not None}
    assert marked == set(CURRENCY_CASE_IDS)


# --- score_currency behaviour ---


def test_returns_none_for_case_without_markers(gold):
    """A case that doesn't probe currency returns None. None is 'not measured', never 'passed'."""
    assert score_currency(_memo("anything"), gold["ct-employment-deployer"]) is None


def test_stale_memo_naming_repealed_colorado_act_is_caught(gold):
    """The §14 step-2 gate: a hand-written memo describing SB 24-205 must be caught."""
    memo = _memo(
        "Under Colorado SB 24-205, a deployer of a high-risk AI system must use reasonable care to "
        "protect consumers from algorithmic discrimination and complete an impact assessment.",
        "A deployer must notify the Attorney General within 90 days of discovering algorithmic "
        "discrimination.",
    )
    outcome = score_currency(memo, gold["co-employment-deployer"])
    assert outcome is not None
    assert outcome.stale is True
    assert "SB 24-205" in outcome.stale_hits
    assert "impact assessment" in outcome.stale_hits
    assert "algorithmic discrimination" in outcome.stale_hits
    assert "reasonable care" in outcome.stale_hits
    # "90-day" is listed once as a concept; normalization makes it cover the memo's "90 days".
    assert "90-day" in outcome.stale_hits


def test_stale_effective_date_is_reported_separately(gold):
    """'Cites the repealed act' and 'states the wrong date for the live act' are different failures."""
    memo = _memo("The Colorado act takes effect in February 2026.")
    outcome = score_currency(memo, gold["co-employment-deployer"])
    assert outcome is not None
    assert outcome.stale_date_hit is True
    assert outcome.stale is True
    assert outcome.stale_hits == []  # the date fired; no stale-phrase marker did


def test_stale_memo_describing_traiga_1_0_is_caught(gold):
    """The Texas probe: the bill number is unchanged, so the tell is the removed 1.0 duty stack.

    This is also the RECALL check on the two-sided bar. "impact assessment" is disqualified as a TX
    marker (it appears in the gold answer's denial), so this memo must still be caught by the 1.0
    vocabulary that travels with it — TRAIGA 1.0 was the Colorado-style broad law, which is why that
    framing co-occurs. If a realistic stale memo ever stops being caught here, the bar has cost more
    recall than it is worth and the marker set needs widening.
    """
    memo = _memo(
        "Texas TRAIGA requires a deployer of a high-risk AI system to maintain a risk management "
        "policy and to complete an impact assessment before deployment.",
        law_id="tx-traiga",
    )
    outcome = score_currency(memo, gold["tx-employment-deployer"])
    assert outcome is not None
    assert outcome.stale is True
    assert "high-risk" in outcome.stale_hits
    assert "risk management policy" in outcome.stale_hits
    # "impact assessment" is deliberately NOT a TX marker — the memo is caught without it.
    assert "impact assessment" not in outcome.stale_hits


# --- side 2 of the validity bar: a marker must be absent from the case's own gold answer ---


@pytest.mark.parametrize("case_id", CURRENCY_CASE_IDS)
def test_markers_absent_from_the_gold_answer(gold, case_id):
    """A phrase the CORRECT answer uses cannot be evidence of a wrong one.

    The second side of the two-sided bar, and the one with teeth: a substring screen cannot read
    negation, and a correct memo often names a duty precisely in order to DENY it. Texas's gold
    obligation says the Act "imposes no impact-assessment ... duty" — so "impact assessment" is
    disqualified as a TX marker rather than adjudicated by hand.

    Enforced against the real gold, parametrized over both probes, so Colorado's cleanliness is
    pinned rather than a happy accident.
    """
    case = gold[case_id]
    assert case.currency_markers is not None
    answer = _normalize(" ".join(case.expect.obligations))
    for marker in case.currency_markers.stale:
        assert _normalize(marker) not in answer, (
            f"{case_id}: stale marker {marker!r} appears in this case's GOLD (correct) answer. "
            f"A correct memo would trip it. Disqualify the marker — do not hand-adjudicate it."
        )
    if case.currency_markers.stale_effective_date:
        assert _normalize(case.currency_markers.stale_effective_date) not in answer


def test_correct_memo_built_from_the_gold_answer_is_clean(gold):
    """The false-positive direction, end to end: score the gold answer itself, through the metric.

    The bar tests check markers in isolation; this checks the whole metric on a memo made of the
    correct answer. Both probes must come back completely clean. If either doesn't, the headline
    finding is inflated in the direction that flatters Patchwork — the worst way to be wrong here.
    """
    for case_id in CURRENCY_CASE_IDS:
        case = gold[case_id]
        outcome = score_currency(_memo(*case.expect.obligations), case)
        assert outcome is not None
        assert outcome.stale_hits == [], f"{case_id}: correct answer tripped {outcome.stale_hits}"
        assert outcome.stale_date_hit is False
        assert outcome.stale is False


def test_correct_texas_denial_of_a_duty_is_not_flagged(gold):
    """The exact sentence the bar was built for.

    A correct TX memo denies the duties TRAIGA lacks, in the words the gold uses. Before the
    two-sided bar this scored stale (and passed only by the accident of the gold's hyphen). It must
    now come back clean without any human reading it.
    """
    case = gold["tx-employment-deployer"]
    memo = _memo(
        "TRAIGA imposes no impact assessment duty on a private employer, and no consumer notice "
        "or opt-out duty either.",
        law_id="tx-traiga",
    )
    outcome = score_currency(memo, case)
    assert outcome is not None
    assert outcome.stale is False


def test_the_residual_polarity_limit_is_known(gold):
    """What the bar does NOT fix, pinned so it stays deliberate.

    The screen still cannot read polarity. The bar removes the case where that BITES — vocabulary
    the correct answer actually uses — but a model that denies a duty in words the gold never uses
    can still trip a marker. That is what hand-verification and `hit_contexts` are for (§8), and it
    is a far narrower hypothetical than the Texas gold obligation, which was a near-certainty.
    """
    case = gold["tx-employment-deployer"]
    memo = _memo("TRAIGA has no high-risk tier at all.", law_id="tx-traiga")
    outcome = score_currency(memo, case)
    assert outcome is not None
    assert outcome.stale is True  # a false positive a human resolves at a glance...
    assert "no high risk tier" in outcome.hit_contexts["high-risk"]  # ...via the context window


def test_hit_context_shows_surrounding_text(gold):
    """Context is normalized text (hyphens flattened), which is fine — it is read for polarity."""
    memo = _memo("Colorado SB 24-205 requires an impact assessment for high-risk systems.")
    outcome = score_currency(memo, gold["co-employment-deployer"])
    assert outcome is not None
    assert "colorado sb 24 205 requires an impact assessment" in outcome.hit_contexts["SB 24-205"]


# --- the claim pool ---


def test_disclaimer_is_excluded_from_the_claim_pool(gold):
    """Fixed chrome is identical across every arm and is not a claim the model made."""
    memo = ComplianceMemo(
        per_law=[],
        disclaimer="This tool does not perform an impact assessment under SB 24-205.",
    )
    outcome = score_currency(memo, gold["co-employment-deployer"])
    assert outcome is not None
    assert outcome.stale is False


def test_claim_pool_covers_every_model_authored_field():
    """Lossless over the fields the model writes: a marker hiding in `summary` or a deadline still
    counts. Missing a field here would silently under-report the headline metric."""
    memo = ComplianceMemo(
        per_law=[
            LawFinding(
                law_id="co-sb26-189",
                short_name="SHORT_NAME_MARK",
                in_scope="yes",
                why="WHY_MARK",
                obligations=[MemoObligation(text="OB_MARK", citation="CITE_MARK")],
                effective_dates=["DATE_MARK"],
            )
        ],
        next_steps=["NEXT_MARK"],
        summary="SUMMARY_MARK",
        disclaimer="DISCLAIMER_MARK",
    )
    pooled = _memo_claim_text(memo)
    for mark in [
        "short_name_mark",
        "why_mark",
        "ob_mark",
        "cite_mark",
        "date_mark",
        "next_mark",
        "summary_mark",
    ]:
        assert mark in pooled
    assert "disclaimer_mark" not in pooled


def test_matching_survives_line_wraps_and_case():
    """Markers match across the whitespace a real model emits."""
    memo = _memo("An\n  Impact   Assessment\nis required under SB\t24-205.")
    from eval.loader import load_gold as _load

    case = {c.id: c for c in _load()}["co-employment-deployer"]
    outcome = score_currency(memo, case)
    assert outcome is not None
    assert "impact assessment" in outcome.stale_hits
    assert "SB 24-205" in outcome.stale_hits
