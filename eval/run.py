"""Run the eval and print a scorecard.

    python -m eval.run            # deterministic tier — free, offline, no API key
    python -m eval.run --strict   # also exit nonzero if any scope verdict is wrong
    python -m eval.run --judge     # ALSO run the judged tier (citation/groundedness/coverage):
                                   # generates real memos (Sonnet) and judges them (Opus).
                                   # SPENDS API TOKENS; needs LLM_PROVIDER=anthropic + a key.

The judged tier is opt-in on purpose so the everyday `make eval` stays free.
"""

import argparse
import html
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from eval.baseline import produce_baseline_memo
from eval.harness import build_core
from eval.judge import score_groundedness
from eval.loader import load_gold, load_retrieval_gold
from eval.metrics import (
    score_citation_exists,
    score_coverage,
    score_currency,
    score_query_retrieval,
    score_retrieval,
    score_scope,
)
from eval.safety import confirm_spend
from patchwork_assurance.config import settings
from patchwork_assurance.core.llm import LLMError, build_llm
from patchwork_assurance.core.memo import MEMO_RETRIEVAL_K, generate_memo
from patchwork_assurance.core.obs import cost_summary
from patchwork_assurance.core.render import memo_to_html
from patchwork_assurance.core.scope import applicable_laws

RESULTS_DIR = Path(__file__).parent / "results"
_IN_SCOPE = ("yes", "uncertain")

# Phase 14 arms. `--arm` selects ONLY what produces the memo; every downstream scorer, the HTML dump,
# and cost accounting are byte-identical across arms (IMPLEMENTATION §7.1). `patchwork` is today's
# production path, and running it must be byte-identical to today's behaviour (the regression lock).
_ARMS = ("patchwork", "baseline-open", "baseline-primed")

# The 13-case publish set, chosen BEFORE the run to span the currency traps, the do-not-harmonize
# pairs, the operative-term distinctions, a multi-state scenario, and a negative control — not randomly
# sampled (§3.1, §3.3). Frozen here so the selection lives in the repo, not in a shell flag typed once.
# Select it with `--cases phase14`. The negative control is all-"no": the patchwork arm drops it (no
# memo to generate), the baseline arms keep it (over-claiming there is the finding, §7.2).
PHASE14_CASE_IDS = (
    "co-employment-deployer",  # CURRENCY (CO): SB 26-189 vs repealed SB 24-205
    "co-cpa-lending-deployer",  # do-not-harmonize vs CO employment (CO CPA, same state)
    "ct-employment-deployer",  # operative term "substantial factor" (AERDT)
    "ct-ctdpa-lending-deployer",  # do-not-harmonize vs CT employment (CT CTDPA)
    "il-employment-deployer",  # IL HB 3773, effect-based standard
    "il-aivia-video-interview",  # do-not-harmonize: AIVIA is procedural, not a discrimination test
    "nj-employment-deployer",  # N.J.A.C. 13:16, effect-based disparate impact
    "nj-njdpa-insurance-deployer",  # do-not-conflate the two NJ laws
    "ca-employment-deployer",  # CA FEHA ADS regs
    "ca-ccpa-housing-deployer",  # do-not-harmonize: CA's two regimes (CCPA ADMT)
    "tx-employment-deployer",  # CURRENCY (TX): TRAIGA 2.0-vs-1.0, the negative-obligation probe
    "tx-co-multistate",  # multi-state + TX intent test vs CO "materially influence"
    "no-regulating-nexus",  # NEGATIVE CONTROL: nothing applies, catches over-claiming
)

# Rough, deliberately conservative per-case cost for the spend estimate. Used only to make the
# confirmation prompt informative, never to bill. Calibrated to the 2026-06-29 judged run: $4.57 / 25
# cases ≈ $0.18 for the patchwork multi-agent memo + Opus judge (the per-obligation Opus judge is ~2/3
# of it). A baseline arm is one structured model call + the same Opus judge, so it is cheaper; a
# conservative 0.15 keeps the gate honest without under-reporting. RECOMPUTE properly at step 8
# (§15.1) and pass the true figure into confirm_spend — a gate that lies about the estimate is worse
# than no gate.
_EST_USD_PER_JUDGED_CASE = 0.18
_EST_USD_PER_BASELINE_CASE = 0.15


def _est_per_case(arm: str) -> float:
    return _EST_USD_PER_JUDGED_CASE if arm == "patchwork" else _EST_USD_PER_BASELINE_CASE


def _select_cases(cases, core, arm: str):
    """Which cases an arm scores. The in-scope gate short-circuits out-of-scope cases for the PATCHWORK
    arm — the deterministic gate returns "nothing applies" and there is no memo to generate. Baseline
    arms MUST see the all-"no" cases: whether a raw model over-claims on an unregulated business is a
    finding, not a skip (§7.2). The gate is a patchwork-arm optimization, not a property of the
    experiment."""
    if arm == "patchwork":
        return [
            c
            for c in cases
            if any(s.in_scope in _IN_SCOPE for s in applicable_laws(c.situation, core.laws))
        ]
    return cases


def _produce_memo(core, case, arm: str, memo_llm):
    """Generate ONE case's memo for the given arm. This is the ONLY thing `--arm` changes; everything
    downstream is identical (§7.1). arm="patchwork" calls the exact production entry point
    (generate_memo) with no deviation — the regression invariant tested in test_baseline.py."""
    if arm == "patchwork":
        scope = applicable_laws(case.situation, core.laws)
        return generate_memo(case.situation, scope, core.retriever, memo_llm, core.laws)
    primed = core.laws if arm == "baseline-primed" else None
    return produce_baseline_memo(case.situation, memo_llm, primed_laws=primed)


def _is_free_run(memo_model: str) -> bool:
    """A provably-$0 judged run: OpenRouter with only `:free` model ids. The spend gate exists to stop
    accidental PAID spend (the Phase 6 incident); free models can't incur cost, so they don't need the
    attended/typed confirmation. A non-`:free` OpenRouter id or any Anthropic model still goes through
    the full confirm_spend chokepoint. Added 2026-06-24 when OpenRouter free models came online.
    Takes the ACTUAL memo model for the arm (a baseline arm can override settings.memo_model), so the
    free-run detection never reads a model the run isn't using."""
    return settings.llm_provider == "openrouter" and all(
        m.endswith(":free") for m in (memo_model, settings.judge_model)
    )


def _memo_to_html(memo, case_id, cite, grounded, coverage) -> str:
    """Render a generated ComplianceMemo to a readable HTML page for the paid-run dump.

    The judged tier scores memos and otherwise discards them; since the run spends real tokens, we
    persist each memo (eval/results/memos-<ts>/<case>.html) so it can be *read* — and now it opens in
    a browser looking like the real memo/PDF, because the body routes through the SAME shared
    `core.render.memo_to_html` the export uses (no second layout to drift, Phase 11 §8). Only the
    eval-specific wrapper is added here: a scores banner at the top and the raw model JSON at the
    bottom (so nothing is lost). Deterministic — no API calls."""
    # Pass the memo's own deterministic corpus_as_of stamp (like ui/pdf.py does) — otherwise
    # memo_to_html falls back to today's date and the dump misreports corpus currency.
    doc = memo_to_html(memo, corpus_as_of=memo.corpus_as_of)
    scores = (
        '<div style="font-family:monospace;background:#ece2d3;border-radius:6px;'
        'padding:8px 12px;margin:0 0 14px;font-size:9pt">'
        f"eval {html.escape(case_id)} &middot; citations real {cite.valid}/{cite.total} &middot; "
        f"grounded {grounded.grounded_yes}/{grounded.judged} &middot; "
        f"coverage {coverage.covered}/{coverage.total}</div>"
    )
    raw = (
        '<details style="margin-top:18px"><summary>raw memo JSON</summary>'
        f"<pre>{html.escape(memo.model_dump_json(indent=2))}</pre></details>"
    )
    # Inject the eval wrapper into the shared document (single <body>, single closing tag).
    return doc.replace("<body>", f"<body>{scores}", 1).replace("</body>", f"{raw}</body>", 1)


def run_judged(
    core,
    cases,
    *,
    arm: str = "patchwork",
    baseline_model: str | None = None,
    case_ids: tuple[str, ...] | None = None,
    limit: int | None = None,
    offset: int = 0,
    stamp: str | None = None,
) -> None:
    """Tier B: generate a real memo per selected case and judge it. Paid on Anthropic / non-free
    OpenRouter; $0 on OpenRouter `:free` models. `arm` selects only what produces the memo (§7.1):
    "patchwork" is today's production path; "baseline-open"/"baseline-primed" ask a raw frontier model
    (`baseline_model`) the same question with no retrieval. `case_ids` restricts to an explicit set
    (the 13-case phase-14 publish set). `limit` caps the cases run — useful on a free model whose
    shared upstream rate-limits a full burst; `offset`+`limit` carve a disjoint paid batch. `stamp`
    pairs the memo dir with the run's scorecard json (same timestamp)."""
    if settings.llm_provider == "stub":
        print(
            "\n  [judged tier skipped] Set LLM_PROVIDER=anthropic|openrouter to run it.\n"
            "  It generates real memos (memo_model) and judges them (judge_model).\n"
        )
        return

    memo_model = (
        settings.memo_model if arm == "patchwork" else (baseline_model or settings.memo_model)
    )
    if arm != "patchwork" and not baseline_model:
        print(f"  [warn] --arm {arm} with no --baseline-model; falling back to {memo_model}.")

    # Restrict to an explicit publish set first (preserving gold order), THEN apply the arm's case
    # filter: the patchwork arm drops all-"no" cases (no memo to generate), baseline arms keep them so
    # over-claiming on the negative control is measured (§7.2). offset+limit carve a disjoint batch.
    selected = [c for c in cases if c.id in case_ids] if case_ids else list(cases)
    arm_cases = _select_cases(selected, core, arm)
    if offset:
        arm_cases = arm_cases[offset:]
    if limit is not None:
        arm_cases = arm_cases[:limit]

    # Spending goes through one chokepoint (eval/safety.py): hard cap, no-unattended, typed confirm.
    # A provably-free run ($0 OpenRouter :free models) skips the attended/typed layers — there's no
    # money to protect — but the hard cap still applies as a runaway circuit breaker.
    if _is_free_run(memo_model):
        if len(arm_cases) > settings.eval_max_judged_cases:
            print("\n  [blocked] exceeds the hard cap even for a free run.\n")
            return
        print(
            f"\n  [free run] OpenRouter :free models (memo={memo_model}, "
            f"judge={settings.judge_model}) — $0, skipping the spend confirmation.\n"
        )
    elif not confirm_spend(
        description=f"judged eval tier, arm={arm} (generate memos + judge them)",
        units=len(arm_cases),
        cap=settings.eval_max_judged_cases,
        est_cost_usd=len(arm_cases) * _est_per_case(arm),
    ):
        print("  Aborted — no tokens spent.\n")
        return

    memo_llm = build_llm(settings, memo_model)
    judge_llm = build_llm(settings, settings.judge_model)
    print("\n" + "=" * 64)
    print(f"  JUDGED TIER (paid)  —  arm={arm}  memo={memo_model}  judge={settings.judge_model}")
    print("=" * 64)
    stamp = stamp or datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    memo_dir = RESULTS_DIR / f"memos-{stamp}-{arm}"
    memo_dir.mkdir(parents=True, exist_ok=True)
    errors = 0
    # Aggregates: judged-N is reported next to every rate, so 95%-of-2 can never masquerade as
    # 95%-of-120 (§7.3). Currency is the headline metric — a per-case screen, hand-verified at step 9.
    agg = {
        "cite_valid": 0,
        "cite_total": 0,
        "grounded_yes": 0,
        "grounded_judged": 0,
        "coverage_covered": 0,
        "coverage_total": 0,
        "obligations": 0,
    }
    currency_probes: list[dict] = []
    for case in arm_cases:
        # Tolerate a per-case LLM failure (e.g. a transient free-tier 429) — report it and keep going
        # rather than crashing the whole run on one bad call.
        try:
            memo = _produce_memo(core, case, arm, memo_llm)
            cite = score_citation_exists(memo, core.sections, case.id)
            grounded = score_groundedness(memo, core.section_texts, judge_llm, case.id)
            coverage = score_coverage(memo, case.expect.obligations, case_id=case.id)
            currency = score_currency(memo, case)  # None unless this case carries markers
            (memo_dir / f"{case.id.replace('/', '_')}.html").write_text(
                _memo_to_html(memo, case.id, cite, grounded, coverage), encoding="utf-8"
            )
        except LLMError as e:
            errors += 1
            print(f"\n  {case.id}\n    [skipped] LLM error: {str(e)[:160]}")
            continue
        agg["cite_valid"] += cite.valid
        agg["cite_total"] += cite.total
        agg["grounded_yes"] += grounded.grounded_yes
        agg["grounded_judged"] += grounded.judged
        agg["coverage_covered"] += coverage.covered
        agg["coverage_total"] += coverage.total
        agg["obligations"] += sum(len(f.obligations) for f in memo.per_law)
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
        if currency is not None:
            flag = "STALE-FLAG (hand-verify)" if currency.stale else "clean"
            print(
                f"    currency:       {flag}"
                + (f"  hits {currency.stale_hits}" if currency.stale_hits else "")
            )
            currency_probes.append(
                {
                    "case_id": case.id,
                    "stale": currency.stale,
                    "stale_hits": currency.stale_hits,
                    "stale_date_hit": currency.stale_date_hit,
                    "hit_contexts": currency.hit_contexts,
                }
            )
    if errors:
        print(f"\n  ({errors}/{len(arm_cases)} case(s) skipped on LLM errors)")

    # Aggregate scorecard — every rate carries its judged-N denominator (§7.3).
    print("\n" + "-" * 64)
    print(f"  ARM SUMMARY  —  arm={arm}  ({len(arm_cases) - errors} case(s) scored)")
    print(f"    citations real:  {agg['cite_valid']}/{agg['cite_total']}")
    print(f"    grounded(yes):   {agg['grounded_yes']}/{agg['grounded_judged']}")
    print(f"    coverage:        {agg['coverage_covered']}/{agg['coverage_total']}")
    print(f"    obligations:     {agg['obligations']} total")
    if currency_probes:
        flagged = sum(1 for p in currency_probes if p["stale"])
        print(f"    currency probes: {flagged}/{len(currency_probes)} stale-flagged (hand-verify)")
    print("-" * 64)

    print(f"\n  memos written to {memo_dir}  (one .html per case — open them, not just the scores)")
    # Self-report spend so a run never depends on a captured tee log (obs tracks the running total).
    totals = cost_summary()
    print(
        f"\n  run cost:  ${totals['cost_usd']:.4f}  "
        f"({totals['llm_calls']} LLM calls, "
        f"{totals['input_tokens']:,} in / {totals['output_tokens']:,} out tokens)"
    )

    # Persist the arm's aggregate + currency probes so the paid numbers are reproducible in the repo
    # (§3.3 — the full selection and every raw output live in the repo), arm-tagged so arms don't
    # collide. The per-case memo HTML is already on disk; this is the machine-readable scorecard.
    scorecard = RESULTS_DIR / f"judged-{stamp}-{arm}.json"
    scorecard.write_text(
        json.dumps(
            {
                "arm": arm,
                "memo_model": memo_model,
                "judge_model": settings.judge_model,
                "cases": [c.id for c in arm_cases],
                "cases_scored": len(arm_cases) - errors,
                "errors": errors,
                "aggregate": agg,
                "currency_probes": currency_probes,
                "cost_usd": cost_summary()["cost_usd"],
            },
            indent=2,
        )
    )
    print(f"  wrote {scorecard.relative_to(Path.cwd())}\n")


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
    parser.add_argument(
        "--offset",
        type=int,
        default=0,
        help="skip the first N in-scope cases; with --limit, carves out a disjoint paid batch",
    )
    parser.add_argument(
        "--arm",
        choices=_ARMS,
        default="patchwork",
        help="judged-tier memo producer: patchwork (production) | baseline-open | baseline-primed",
    )
    parser.add_argument(
        "--baseline-model",
        default=None,
        help="model id for the baseline arms (e.g. openai/gpt-5.6-sol); ignored for --arm patchwork",
    )
    parser.add_argument(
        "--cases",
        default=None,
        help="restrict judged tier to a case set: 'phase14' (the 13-case publish set) or a "
        "comma-separated list of gold case ids",
    )
    args = parser.parse_args()

    case_ids: tuple[str, ...] | None = None
    if args.cases:
        case_ids = (
            PHASE14_CASE_IDS
            if args.cases == "phase14"
            else tuple(c.strip() for c in args.cases.split(",") if c.strip())
        )

    core = build_core()
    cases = load_gold()

    # Fail loud on a mistyped --cases id rather than silently scoring a smaller set.
    if case_ids:
        known = {c.id for c in cases}
        unknown = [cid for cid in case_ids if cid not in known]
        if unknown:
            parser.error(f"--cases: unknown gold case id(s): {', '.join(unknown)}")

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
        run_judged(
            core,
            cases,
            arm=args.arm,
            baseline_model=args.baseline_model,
            case_ids=case_ids,
            limit=args.limit,
            offset=args.offset,
            stamp=stamp,
        )

    if args.strict and scope_correct < scope_total:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
