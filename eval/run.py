"""Run the deterministic eval tier and print a scorecard. Free, offline, no API key.

    python -m eval.run            # scorecard to stdout + a JSON sidecar under eval/results/
    python -m eval.run --strict   # also exit nonzero if any scope verdict is wrong

The judged tier (citation groundedness / obligation coverage) is added later behind --judge
(phase-6 IMPLEMENTATION §6); it spends API tokens, so it is deliberately not part of this command.
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from eval.harness import build_core
from eval.loader import load_gold
from eval.metrics import score_retrieval, score_scope
from patchwork_assurance.core.memo import MEMO_RETRIEVAL_K

RESULTS_DIR = Path(__file__).parent / "results"


def main() -> int:
    parser = argparse.ArgumentParser(description="Patchwork eval — deterministic tier")
    parser.add_argument("--strict", action="store_true", help="exit nonzero on any scope miss")
    parser.add_argument(
        "--k", type=int, default=MEMO_RETRIEVAL_K, help="retrieval top-k (defaults to the memo's k)"
    )
    args = parser.parse_args()

    core = build_core()
    cases = load_gold()

    scope_correct = scope_total = 0
    scope_failures: list[str] = []
    recalls: list[float] = []
    retrieval_lines: list[str] = []

    for case in cases:
        scope = score_scope(case, core)
        scope_correct += scope.correct
        scope_total += scope.total
        if scope.correct < scope.total:
            for law_id, want in scope.expected.items():
                if scope.got.get(law_id) != want:
                    scope_failures.append(
                        f"    {case.id}: {law_id} expected {want!r}, got {scope.got.get(law_id)!r}"
                    )

        retrieval = score_retrieval(case, core, args.k)
        if retrieval is not None:
            recalls.append(retrieval.recall)
            mark = "ok  " if retrieval.recall == 1.0 else "MISS"
            line = f"    {mark} {case.id}: {len(retrieval.hit)}/{len(retrieval.want)}"
            if retrieval.missed:
                line += f"   missing {retrieval.missed}"
            retrieval_lines.append(line)

    scope_acc = scope_correct / scope_total if scope_total else 0.0
    mean_recall = sum(recalls) / len(recalls) if recalls else 0.0

    print("=" * 64)
    print("PATCHWORK EVAL  —  deterministic tier (free, offline)")
    print("=" * 64)
    print(f"\n  Scope accuracy:      {scope_correct}/{scope_total} = {scope_acc:.1%}")
    if scope_failures:
        print("  scope failures:")
        print("\n".join(scope_failures))
    print(
        f"\n  Retrieval recall@{args.k}:  mean {mean_recall:.1%} over {len(recalls)} in-scope cases"
    )
    print("\n".join(retrieval_lines))
    print()

    RESULTS_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    out = RESULTS_DIR / f"{stamp}.json"
    out.write_text(
        json.dumps(
            {
                "n_cases": len(cases),
                "k": args.k,
                "scope_accuracy": scope_acc,
                "scope_correct": scope_correct,
                "scope_total": scope_total,
                "scope_failures": scope_failures,
                "retrieval_recall_at_k": mean_recall,
                "retrieval_cases_scored": len(recalls),
            },
            indent=2,
        )
    )
    print(f"  wrote {out.relative_to(Path.cwd())}\n")

    if args.strict and scope_correct < scope_total:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
