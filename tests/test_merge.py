"""Batched paid runs write one scorecard per invocation; these pin how they recombine (phase-14 §15)."""

import pytest
from eval.merge import MergeConflict, format_summary, merge_scorecards

_PROV = {"git_sha": "abc123", "corpus_as_of": "2026-07-03"}


def _card(**over):
    card = {
        "arm": "grounded-single",
        "run_stamp": "20260720T000000Z",
        "stub_dry_run": False,
        "provenance": _PROV,
        "memo_model": "openai/gpt-5.6-sol",
        "judge_model": "anthropic/claude-opus-4.8",
        "groundedness_scored": False,
        "groundedness_denominator": None,
        "cross_judge_model": None,
        "cases_scored": 6,
        "errors": 0,
        "aggregate": {
            "cite_valid": 10,
            "cite_total": 12,
            "coverage_covered": 4,
            "coverage_total": 8,
        },
        "cross_disagreements": [],
        "currency_probes": [{"case_id": "co-employment-deployer", "stale": False}],
        "cost_usd": 1.5,
        "unknown_rate_calls": 0,
        "input_tokens": 1000,
        "output_tokens": 2000,
    }
    card.update(over)
    return card


def test_counts_and_cost_add_across_batches():
    merged = merge_scorecards([_card(), _card(run_stamp="20260720T010000Z")])
    assert merged["cases_scored"] == 12
    assert merged["batches"] == 2
    assert merged["aggregate"]["cite_valid"] == 20
    assert merged["aggregate"]["cite_total"] == 24
    # Cost is what makes the merged file the arm's provenance record — it must not be dropped.
    assert merged["cost_usd"] == 3.0
    assert merged["input_tokens"] == 2000
    assert merged["output_tokens"] == 4000


def test_currency_probes_concatenate_rather_than_collapse():
    merged = merge_scorecards(
        [
            _card(),
            _card(
                run_stamp="20260720T010000Z",
                currency_probes=[{"case_id": "tx-employment-deployer", "stale": True}],
            ),
        ]
    )
    assert len(merged["currency_probes"]) == 2
    assert "1/2 stale-flagged" in format_summary(merged)


@pytest.mark.parametrize(
    "field,value",
    [
        ("arm", "patchwork"),
        ("memo_model", "anthropic/claude-fable-5"),
        ("judge_model", "anthropic/claude-sonnet-5"),
        ("groundedness_scored", True),
        ("stub_dry_run", True),
    ],
)
def test_refuses_to_merge_different_experiments(field, value):
    with pytest.raises(MergeConflict, match=field):
        merge_scorecards([_card(), _card(**{field: value})])


def test_refuses_to_merge_across_a_different_corpus_or_sha():
    # Summing across a re-ingested corpus or a different SHA would bury the fact that the numbers
    # were not produced by the same system.
    other = _card(provenance={"git_sha": "def456", "corpus_as_of": "2026-07-03"})
    with pytest.raises(MergeConflict, match="provenance"):
        merge_scorecards([_card(), other])


def test_rates_are_computed_once_from_summed_counts():
    # 10/12 and 1/2 must merge to 11/14 (78.6%), never to the mean of 83.3% and 50%.
    merged = merge_scorecards(
        [
            _card(),
            _card(
                run_stamp="20260720T010000Z",
                aggregate={
                    "cite_valid": 1,
                    "cite_total": 2,
                    "coverage_covered": 0,
                    "coverage_total": 1,
                },
            ),
        ]
    )
    assert "11/14 = 78.6%" in format_summary(merged)


def test_empty_input_is_an_error_not_an_empty_scorecard():
    with pytest.raises(MergeConflict):
        merge_scorecards([])
