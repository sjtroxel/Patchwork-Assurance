"""Combine the per-batch scorecards a batched paid run produces into one arm-level scorecard.

Step 8 runs each arm in batches (`--limit`/`--offset`) so the bill can be checked between them — that
is the layer that actually protects the budget (§15). But `run_judged` writes one scorecard per
INVOCATION, so a batched arm ends up as N partial files and nothing downstream knows how to read them
as one arm. This closes that gap.

Every aggregate the harness reports is a raw COUNT (cite_valid / cite_total, coverage_covered /
coverage_total, ...), never a pre-divided rate, so merging is addition and the arm-level rate is
computed once at the end. That is why the metrics were built as counts; keep it that way.

Refuses to merge scorecards that disagree on anything that would make the sum a lie — a different arm,
model, judge, corpus, or git SHA is a different experiment, not another batch of the same one (§12).

    python -m eval.merge eval/results/judged-*-grounded-single.json -o merged.json
"""

import argparse
import json
from pathlib import Path
from typing import Any

# Identity of the experiment. If any of these differ across batches, the runs are not the same arm and
# summing them would silently fabricate a result.
_MUST_MATCH = (
    "arm",
    "memo_model",
    "judge_model",
    "groundedness_scored",
    "groundedness_denominator",
    "cross_judge_model",
    "stub_dry_run",
)
# Top-level totals that add. Token counts and cost make the merged file the provenance record for the
# whole arm (§12), which is the point of merging at all.
_SUM_KEYS = (
    "cases_scored",
    "errors",
    "cost_usd",
    "unknown_rate_calls",
    "input_tokens",
    "output_tokens",
)
_CONCAT_KEYS = ("cross_disagreements", "currency_probes")


class MergeConflict(ValueError):
    """Raised when scorecards describe different experiments."""


def merge_scorecards(cards: list[dict[str, Any]]) -> dict[str, Any]:
    """Merge N per-batch scorecards for the SAME arm into one. Raises MergeConflict on a mismatch."""
    if not cards:
        raise MergeConflict("nothing to merge")

    head = cards[0]
    for key in _MUST_MATCH:
        values = {json.dumps(c.get(key), sort_keys=True) for c in cards}
        if len(values) > 1:
            raise MergeConflict(f"scorecards disagree on {key!r}: {sorted(values)}")

    # Provenance is the corpus + code the numbers were produced by. A batch run against a different
    # SHA or a re-ingested corpus is not comparable, and merging it would bury that fact.
    provenances = {json.dumps(c.get("provenance"), sort_keys=True) for c in cards}
    if len(provenances) > 1:
        raise MergeConflict(
            "scorecards disagree on provenance (git_sha / corpus) — these are different experiments"
        )

    merged: dict[str, Any] = {k: head.get(k) for k in _MUST_MATCH}
    merged["provenance"] = head.get("provenance")
    merged["merged_from"] = sorted(c.get("run_stamp", "?") for c in cards)
    merged["batches"] = len(cards)

    for key in _SUM_KEYS:
        if any(key in c for c in cards):
            merged[key] = sum(c.get(key, 0) or 0 for c in cards)

    agg: dict[str, int] = {}
    for card in cards:
        for key, value in (card.get("aggregate") or {}).items():
            agg[key] = agg.get(key, 0) + value
    merged["aggregate"] = agg

    for key in _CONCAT_KEYS:
        merged[key] = [item for c in cards for item in (c.get(key) or [])]

    return merged


def _rate(num: int, den: int) -> str:
    return f"{num}/{den} = {num / den * 100:.1f}%" if den else f"{num}/{den} = n/a"


def format_summary(merged: dict[str, Any]) -> str:
    """The arm-level numbers, computed from summed counts exactly once."""
    agg = merged["aggregate"]
    stale = sum(1 for p in merged.get("currency_probes", []) if p.get("stale"))
    probes = len(merged.get("currency_probes", []))
    lines = [
        f"  ARM {merged['arm']}  memo={merged['memo_model']}  "
        f"({merged['batches']} batches, {merged['cases_scored']} cases, {merged['errors']} errors)",
        f"    citations real:  {_rate(agg.get('cite_valid', 0), agg.get('cite_total', 0))}",
        f"    grounded(yes):   {_rate(agg.get('grounded_yes', 0), agg.get('grounded_judged', 0))}",
        f"    coverage:        {_rate(agg.get('coverage_covered', 0), agg.get('coverage_total', 0))}",
        f"    obligations:     {agg.get('obligations', 0)} total",
        f"    currency probes: {stale}/{probes} stale-flagged",
    ]
    cost = merged.get("cost_usd")
    if cost is not None:
        unpriced = merged.get("unknown_rate_calls", 0)
        floor = "  (FLOOR — unpriced calls present)" if unpriced else ""
        lines.append(
            f"    arm cost:        ${cost:.4f}{floor}  "
            f"({merged.get('input_tokens', 0):,} in / {merged.get('output_tokens', 0):,} out)"
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge batched judged scorecards for one arm.")
    parser.add_argument("scorecards", nargs="+", type=Path, help="judged-*.json files for ONE arm")
    parser.add_argument("-o", "--out", type=Path, help="write the merged scorecard here")
    args = parser.parse_args()

    cards = [json.loads(p.read_text(encoding="utf-8")) for p in args.scorecards]
    merged = merge_scorecards(cards)
    print(format_summary(merged))
    if args.out:
        args.out.write_text(json.dumps(merged, indent=2), encoding="utf-8")
        print(f"\n  wrote {args.out}")


if __name__ == "__main__":
    main()
