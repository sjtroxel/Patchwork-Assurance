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
from eval.loader import load_gold, load_retrieval_gold
from eval.metrics import (
    score_citation_exists,
    score_coverage,
    score_query_retrieval,
    score_retrieval,
    score_scope,
)
from eval.safety import confirm_spend
from patchwork_assurance.config import settings
from patchwork_assurance.core.llm import LLMError, build_llm
from patchwork_assurance.core.memo import MEMO_RETRIEVAL_K, generate_memo
from patchwork_assurance.core.scope import applicable_laws

RESULTS_DIR = Path(__file__).parent / "results"
_IN_SCOPE = ("yes", "uncertain")
# Rough, deliberately conservative per-case cost for the spend estimate (one Sonnet memo + a few
# Opus judge calls). Used only to make the confirmation prompt informative, never to bill.
_EST_USD_PER_JUDGED_CASE = 0.10


def _is_free_run() -> bool:
    """A provably-$0 judged run: OpenRouter with only `:free` model ids. The spend gate exists to stop
    accidental PAID spend (the Phase 6 incident); free models can't incur cost, so they don't need the
    attended/typed confirmation. A non-`:free` OpenRouter id or any Anthropic model still goes through
    the full confirm_spend chokepoint. Added 2026-06-24 when OpenRouter free models came online."""
    return settings.llm_provider == "openrouter" and all(
        m.endswith(":free") for m in (settings.memo_model, settings.judge_model)
    )


def run_judged(core, cases, limit: int | None = None) -> None:
    """Tier B: generate a real memo per in-scope case and judge it. Paid on Anthropic / non-free
    OpenRouter; $0 on OpenRouter `:free` models. `limit` caps the cases run — useful on a free model
    whose shared upstream rate-limits a full 14-case burst (run a few at a time)."""
    if settings.llm_provider == "stub":
        print(
            "\n  [judged tier skipped] Set LLM_PROVIDER=anthropic|openrouter to run it.\n"
            "  It generates real memos (memo_model) and judges them (judge_model).\n"
        )
        return

    in_scope_cases = [
        case
        for case in cases
        if any(s.in_scope in _IN_SCOPE for s in applicable_laws(case.situation, core.laws))
    ]
    if limit is not None:
        in_scope_cases = in_scope_cases[:limit]

    # Spending goes through one chokepoint (eval/safety.py): hard cap, no-unattended, typed confirm.
    # A provably-free run ($0 OpenRouter :free models) skips the attended/typed layers — there's no
    # money to protect — but the hard cap still applies as a runaway circuit breaker.
    if _is_free_run():
        if len(in_scope_cases) > settings.eval_max_judged_cases:
            print("\n  [blocked] exceeds the hard cap even for a free run.\n")
            return
        print(
            f"\n  [free run] OpenRouter :free models (memo={settings.memo_model}, "
            f"judge={settings.judge_model}) — $0, skipping the spend confirmation.\n"
        )
    elif not confirm_spend(
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
    errors = 0
    for case in in_scope_cases:
        # Tolerate a per-case LLM failure (e.g. a transient free-tier 429) — report it and keep going
        # rather than crashing the whole run on one bad call.
        try:
            scope = applicable_laws(case.situation, core.laws)
            memo = generate_memo(case.situation, scope, core.retriever, memo_llm, core.laws)
            cite = score_citation_exists(memo, core.sections, case.id)
            grounded = score_groundedness(memo, core.section_texts, judge_llm, case.id)
            coverage = score_coverage(memo, case.expect.obligations, case_id=case.id)
        except LLMError as e:
            errors += 1
            print(f"\n  {case.id}\n    [skipped] LLM error: {str(e)[:160]}")
            continue
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
    if errors:
        print(f"\n  ({errors}/{len(in_scope_cases)} case(s) skipped on LLM errors)")


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
        "--mode",
        default=settings.retrieval_mode,
        help="retrieval mode: semantic|filtered|hybrid|routed",
    )
    parser.add_argument(
        "--sweep",
        action="store_true",
        help="compare semantic|filtered|hybrid|routed recall (free, deterministic — the Phase 8 ladder)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="cap judged-tier cases (helps under a free model's upstream rate limit)",
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

    modes = ["semantic", "filtered", "hybrid", "routed"] if args.sweep else [args.mode]
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

        # Exact-term / citation gold set — the queries where lexical/hybrid/routed can beat semantic.
        q_cases = load_retrieval_gold()
        q_recalls: dict[str, float] = {}
        for mode in modes:
            outcomes = [score_query_retrieval(qc, core, args.k, mode) for qc in q_cases]
            q_recalls[mode] = sum(o.recall for o in outcomes) / len(outcomes)
        print(f"\n  Exact-term / citation queries (mean recall@{args.k}, {len(q_cases)} cases):")
        for mode in modes:
            print(f"    {mode:9} {q_recalls[mode]:.1%}")
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
        run_judged(core, cases, limit=args.limit)

    if args.strict and scope_correct < scope_total:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
