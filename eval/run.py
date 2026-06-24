"""Run the eval and print a scorecard.

    python -m eval.run            # deterministic tier — free, offline, no API key
    python -m eval.run --strict   # also exit nonzero if any scope verdict is wrong
    python -m eval.run --judge     # ALSO run the judged tier (citation/groundedness/coverage):
                                   # generates real memos (Sonnet) and judges them (Opus).
                                   # SPENDS API TOKENS; needs LLM_PROVIDER=anthropic + a key.

The judged tier is opt-in on purpose so the everyday `make eval` stays free.
"""

import argparse
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from eval.harness import build_core
from eval.judge import score_groundedness
from eval.loader import load_gold
from eval.metrics import score_citation_exists, score_coverage, score_retrieval, score_scope
from eval.safety import confirm_spend
from patchwork_assurance.config import settings
from patchwork_assurance.core.llm import build_llm
from patchwork_assurance.core.memo import MEMO_RETRIEVAL_K, generate_memo
from patchwork_assurance.core.scope import applicable_laws

RESULTS_DIR = Path(__file__).parent / "results"
_IN_SCOPE = ("yes", "uncertain")
# Rough, deliberately conservative per-case cost for the spend estimate (one Sonnet memo + a few
# Opus judge calls). Used only to make the confirmation prompt informative, never to bill.
_EST_USD_PER_JUDGED_CASE = 0.10


def run_judged(core, cases) -> None:
    """Tier B: generate a real memo per in-scope case (Sonnet) and judge it (Opus). Paid."""
    if settings.llm_provider == "stub":
        print(
            "\n  [judged tier skipped] Set LLM_PROVIDER=anthropic + ANTHROPIC_API_KEY to run it.\n"
            "  It generates real memos (Sonnet) and judges them (Opus) — it spends tokens.\n"
        )
        return

    in_scope_cases = [
        case
        for case in cases
        if any(s.in_scope in _IN_SCOPE for s in applicable_laws(case.situation, core.laws))
    ]

    # All spending goes through one chokepoint (eval/safety.py): hard cap, then no-unattended,
    # then typed confirmation with a cost estimate. The estimate is rough — one Sonnet memo plus a
    # few Opus judge calls per case — and exists to make the spend visible, not to be exact.
    if not confirm_spend(
        description="judged eval tier (generate memos + judge them)",
        units=len(in_scope_cases),
        cap=settings.eval_max_judged_cases,
        est_cost_usd=len(in_scope_cases) * _EST_USD_PER_JUDGED_CASE,
    ):
        print("  Aborted — no tokens spent.\n")
        return

    memo_llm = build_llm(settings, settings.memo_model)
    judge_llm = build_llm(settings, settings.judge_model)
    print("\n" + "=" * 64)
    print(f"  JUDGED TIER (paid)  —  memo={settings.memo_model}  judge={settings.judge_model}")
    print("=" * 64)
    for case in in_scope_cases:
        scope = applicable_laws(case.situation, core.laws)
        memo = generate_memo(case.situation, scope, core.retriever, memo_llm, core.laws)
        cite = score_citation_exists(memo, core.sections, case.id)
        grounded = score_groundedness(memo, core.section_texts, judge_llm, case.id)
        coverage = score_coverage(memo, case.expect.obligations, case_id=case.id)
        print(f"\n  {case.id}")
        print(
            f"    citations real: {cite.valid}/{cite.total}"
            + (f"  bad {cite.invalid}" if cite.invalid else "")
        )
        print(f"    grounded(yes):  {grounded.grounded_yes}/{grounded.judged}")
        print(
            f"    coverage:       {coverage.covered}/{coverage.total}"
            + (f"  missed {coverage.missed}" if coverage.missed else "")
        )


def _retrieval(core, cases, k: int, mode: str) -> tuple[float, int, list[str]]:
    """Mean recall@k for one retrieval mode (free, deterministic), plus per-case lines."""
    recalls: list[float] = []
    lines: list[str] = []
    for case in cases:
        outcome = score_retrieval(case, core, k, mode)
        if outcome is None:
            continue
        recalls.append(outcome.recall)
        mark = "ok  " if outcome.recall == 1.0 else "MISS"
        line = f"    {mark} {case.id}: {len(outcome.hit)}/{len(outcome.want)}"
        if outcome.missed:
            line += f"   missing {outcome.missed}"
        lines.append(line)
    mean = sum(recalls) / len(recalls) if recalls else 0.0
    return mean, len(recalls), lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Patchwork eval — deterministic tier")
    parser.add_argument("--strict", action="store_true", help="exit nonzero on any scope miss")
    parser.add_argument(
        "--judge", action="store_true", help="also run the paid judged tier (spends tokens)"
    )
    parser.add_argument(
        "--k", type=int, default=MEMO_RETRIEVAL_K, help="retrieval top-k (defaults to the memo's k)"
    )
    parser.add_argument(
        "--mode", default=settings.retrieval_mode, help="retrieval mode: semantic|filtered|hybrid"
    )
    parser.add_argument(
        "--sweep",
        action="store_true",
        help="compare semantic|filtered|hybrid recall (free, deterministic — the Phase 8 ladder)",
    )
    args = parser.parse_args()

    core = build_core()
    cases = load_gold()

    # Scope accuracy is retrieval-mode-independent — compute it once.
    scope_correct = scope_total = 0
    scope_failures: list[str] = []
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
    scope_acc = scope_correct / scope_total if scope_total else 0.0

    print("=" * 64)
    print("PATCHWORK EVAL  —  deterministic tier (free, offline)")
    print("=" * 64)
    print(f"\n  Scope accuracy:      {scope_correct}/{scope_total} = {scope_acc:.1%}")
    if scope_failures:
        print("  scope failures:")
        print("\n".join(scope_failures))

    modes = ["semantic", "filtered", "hybrid"] if args.sweep else [args.mode]
    mode_recalls: dict[str, float] = {}
    cases_scored = 0
    for mode in modes:
        mean, n, lines = _retrieval(core, cases, args.k, mode)
        mode_recalls[mode] = mean
        cases_scored = n
        print(f"\n  Retrieval recall@{args.k} [{mode}]:  mean {mean:.1%} over {n} in-scope cases")
        if not args.sweep:
            print("\n".join(lines))
    if args.sweep:
        print(f"\n  Sweep comparison (mean recall@{args.k}):")
        for mode in modes:
            print(f"    {mode:9} {mode_recalls[mode]:.1%}")
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
                "retrieval_modes": mode_recalls,
                "retrieval_recall_at_k": mode_recalls.get(
                    args.mode, next(iter(mode_recalls.values()))
                ),
                "retrieval_cases_scored": cases_scored,
            },
            indent=2,
        )
    )
    print(f"  wrote {out.relative_to(Path.cwd())}\n")

    if args.judge or settings.eval_use_judge:
        run_judged(core, cases)

    if args.strict and scope_correct < scope_total:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
