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
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from eval.baseline import produce_baseline_memo
from eval.harness import build_core
from eval.judge import GroundednessOutcome, score_groundedness
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
# `grounded-single` is the SAME corpus, gate, retrieval, law facts, and prompt as production, generated
# in ONE single-pass call by whatever model `--baseline-model` names. It carries two jobs depending on
# that model, and the arm code is identical for both (§1.2, amended 2026-07-19):
#   deepseek  -> the D4 ablation: does the multi-agent pipeline beat one cheap call on the same corpus?
#   sol/fable -> THE HEADLINE head-to-head: given the identical statutes Patchwork retrieves, does the
#                curated corpus + multi-agent pipeline still beat handing the best frontier model the
#                same text? Both sides read the same statutes, so training-cutoff staleness cannot
#                explain the result — which is the entire point of the amendment.
_ARMS = ("patchwork", "baseline-open", "baseline-primed", "grounded-single")

# Arms that run the deterministic scope gate and retrieve from the corpus. Two things follow from
# membership, and both exist to keep a comparison symmetric rather than to flatter an arm:
#   1. Case selection — a gated arm generates no memo when the gate says nothing applies (§7.2).
#   2. Groundedness denominator — decision #2 counts an unresolvable citation as not-grounded for RAW
#      arms, because a raw model's worst currency failures ARE the cites that don't resolve. A grounded
#      arm cites our own corpus, so an unresolvable cite there is a rare pipeline defect, not a
#      currency failure. Applying the strict denominator to grounded-single while patchwork keeps the
#      skip would handicap the ablation in exactly the comparison D4 exists to make, which is the
#      "fix only the traps that hurt us" failure §11 warns about. Both grounded arms use the same rule.
_GATED_ARMS = ("patchwork", "grounded-single")

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
# A grounded arm feeds the model every in-scope law's retrieved excerpts, so its INPUT is an order of
# magnitude larger than a baseline arm's prose-only prompt (a multi-state case can run tens of
# thousands of input tokens). On a frontier model at $5-10/M in, that input — not the generation — is
# the bill. Deliberately the most conservative rate in the table; recompute with real token counts at
# step 8 (§15.1) rather than trusting it.
_EST_USD_PER_GROUNDED_CASE = 0.30
# Cross-judge (§10 trap 4) re-judges ~20% of locatable obligations with a second-lab judge — a modest
# add-on of paid judge calls. A conservative +20% per-case bump keeps the spend gate honest; recompute
# with real token counts at step 8 like everything else. Default second judge = a different lab from
# the Opus primary, which is the whole point of the cross-check.
_EST_CROSS_JUDGE_BUMP = 1.20
# Share of a judged case that is NOT the Opus groundedness judge (generation + deterministic scoring).
# Used only when --no-groundedness skips the judge. Rough; step 7's smoke test replaces it.
_EST_NO_JUDGE_FACTOR = 0.40
_DEFAULT_CROSS_JUDGE_MODEL = "openai/gpt-5.6-sol"


def _est_per_case(arm: str) -> float:
    """Per-case estimate for the spend gate. Three rates, because the arms have genuinely different
    cost shapes: patchwork fans out per law, a grounded arm pays for a large statute-excerpt prompt on
    whatever model it is pointed at, and a baseline arm sends prose only."""
    if arm == "patchwork":
        return _EST_USD_PER_JUDGED_CASE
    if arm in _GATED_ARMS:  # grounded, single-pass: excerpt-heavy input dominates
        return _EST_USD_PER_GROUNDED_CASE
    return _EST_USD_PER_BASELINE_CASE


def _git_sha() -> str:
    """The commit the run's code came from. Read-only (never mutates history). 'unknown' if git is
    unavailable — provenance degrades, it never crashes the run."""
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except Exception:
        return "unknown"


def _run_provenance(core) -> dict:
    """Run-level provenance for the scorecard (§12): the exact code + corpus the numbers came from, so
    an artifact is reproducible from the repo without a separate log (Phase 12 lost its tee log to a
    path typo). Recorded on every run, dry or paid. The corpus is recorded at the RUN level — not read
    off a memo — because baseline arms never touch the corpus and carry a null corpus_as_of, yet the
    run was still configured against these laws."""
    laws = sorted(core.laws, key=lambda law: law.law_id)
    retrieved = [law.retrieved_on for law in laws if getattr(law, "retrieved_on", None)]
    return {
        "git_sha": _git_sha(),
        "corpus_as_of": max(retrieved).isoformat() if retrieved else None,
        "corpus_laws": [
            {
                "law_id": law.law_id,
                "retrieved_on": (
                    law.retrieved_on.isoformat() if getattr(law, "retrieved_on", None) else None
                ),
            }
            for law in laws
        ],
    }


def _select_cases(cases, core, arm: str):
    """Which cases an arm scores. The in-scope gate short-circuits out-of-scope cases for the GATED
    arms (patchwork, grounded-single) — the deterministic gate returns "nothing applies" and there is no
    memo to generate. Baseline arms MUST see the all-"no" cases: whether a raw model over-claims on an
    unregulated business is a finding, not a skip (§7.2). The gate is an optimization of the arms that
    have one, not a property of the experiment."""
    if arm in _GATED_ARMS:
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
    if arm == "grounded-single":
        # The D4 ablation. Everything Patchwork brings EXCEPT the multi-agent pipeline: the same
        # deterministic gate, the same retrieval, the same law facts, the same frozen production
        # prompt, the same deterministic overlays — generated in one single-pass call by a cheap
        # model. Deliberately NOT a new producer with its own prompt: a fresh prompt would add a
        # second variable and make the ablation unreadable. `pipeline="single"` is injected rather
        # than set in settings so production config is untouched for the rest of the run.
        scope = applicable_laws(case.situation, core.laws)
        return generate_memo(
            case.situation, scope, core.retriever, memo_llm, core.laws, pipeline="single"
        )
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
    cross_judge_model: str | None = None,
    stub_dry_run: bool = False,
    score_grounded: bool = True,
) -> None:
    """Tier B: generate a real memo per selected case and judge it. Paid on Anthropic / non-free
    OpenRouter; $0 on OpenRouter `:free` models. `arm` selects only what produces the memo (§7.1):
    "patchwork" is today's production path; "baseline-open"/"baseline-primed" ask a raw frontier model
    (`baseline_model`) the same question with no retrieval; "grounded-single" is the D4 ablation, the
    production corpus and gate with one cheap single-pass call. `case_ids` restricts to an explicit set
    (the 13-case phase-14 publish set). `limit` caps the cases run — useful on a free model whose
    shared upstream rate-limits a full burst; `offset`+`limit` carve a disjoint paid batch. `stamp`
    pairs the memo dir with the run's scorecard json (same timestamp). `cross_judge_model` (§10 trap 4)
    turns on the second-lab cross-judge over ~20% of locatable obligations; None leaves it off.
    `score_grounded=False` (`--no-groundedness`) generates and scores everything DETERMINISTIC —
    citations, coverage, currency, the memo HTML — without paying the Opus judge, which is ~2/3 of a
    judged case. This is what makes D1 ("core run only; judged tier built but NOT run") actually
    executable: before it existed, `--judge` bought the judge unconditionally and the documented
    core/judged spend split could not be performed.
    `stub_dry_run` (§13, build-order step 5) runs the WHOLE judged pipeline — arm dispatch, currency,
    groundedness, cross-judge, artifacts, provenance — on `StubLLM` at $0, so the wiring can be
    exercised end-to-end offline before a paid call. It requires `LLM_PROVIDER=stub` (fail loud
    otherwise: a "dry run" that quietly spent real money would be the worst outcome)."""
    if stub_dry_run and settings.llm_provider != "stub":
        raise SystemExit(
            "  --stub-judged requires LLM_PROVIDER=stub (a dry run must not reach a paid provider)."
        )
    if settings.llm_provider == "stub" and not stub_dry_run:
        print(
            "\n  [judged tier skipped] Set LLM_PROVIDER=anthropic|openrouter to run it, or pass\n"
            "  --stub-judged to exercise the whole pipeline offline on StubLLM at $0 (a dry run).\n"
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

    # Cross-judge (§10 trap 4) adds a second-lab judge over ~20% of obligations — more paid calls, so
    # the estimate carries a conservative bump before it reaches the gate.
    est_cost = len(arm_cases) * _est_per_case(arm)
    if not score_grounded:
        # The per-obligation Opus judge is roughly 2/3 of a judged case (see the calibration note on
        # _EST_USD_PER_JUDGED_CASE), so generation + deterministic scoring is the remainder. Rough on
        # purpose; the smoke test at step 7 replaces it with a measured figure.
        est_cost *= _EST_NO_JUDGE_FACTOR
    if cross_judge_model:
        est_cost *= _EST_CROSS_JUDGE_BUMP

    # Spending goes through one chokepoint (eval/safety.py): hard cap, no-unattended, typed confirm.
    # A provably-free run ($0 OpenRouter :free models) skips the attended/typed layers — there's no
    # money to protect — but the hard cap still applies as a runaway circuit breaker.
    if stub_dry_run:
        # Offline StubLLM run: no provider is contacted, so there is no money to protect. The hard cap
        # still guards a runaway case count.
        if len(arm_cases) > settings.eval_max_judged_cases:
            print("\n  [blocked] exceeds the hard cap even for a stub dry run.\n")
            return
        print("\n  [stub dry run] offline StubLLM — $0, no memo/judge model contacted.\n")
    elif _is_free_run(memo_model):
        if len(arm_cases) > settings.eval_max_judged_cases:
            print("\n  [blocked] exceeds the hard cap even for a free run.\n")
            return
        print(
            f"\n  [free run] OpenRouter :free models (memo={memo_model}, "
            f"judge={settings.judge_model}) — $0, skipping the spend confirmation.\n"
        )
    elif not confirm_spend(
        description=f"judged eval tier, arm={arm} (generate memos + judge them)"
        + (f" + cross-judge {cross_judge_model}" if cross_judge_model else ""),
        units=len(arm_cases),
        cap=settings.eval_max_judged_cases,
        est_cost_usd=est_cost,
    ):
        print("  Aborted — no tokens spent.\n")
        return

    memo_llm = build_llm(settings, memo_model)
    judge_llm = build_llm(settings, settings.judge_model)
    # A different lab from the Opus primary judge — that difference is the entire point of the
    # cross-check. Built once and reused across cases; None leaves cross-judging off (D1: built this
    # phase, decided separately before it is run).
    cross_judge_llm = build_llm(settings, cross_judge_model) if cross_judge_model else None
    # Raw (ungrounded) arms count unresolvable citations as not-grounded (decision #2); the grounded
    # arms keep the skip — patchwork because its arm must stay byte-identical to today (the regression
    # lock, §7.1), grounded-single so the D4 ablation is measured on the same denominator as the arm it
    # is being compared against (see _GATED_ARMS).
    count_unresolvable = arm not in _GATED_ARMS
    print("\n" + "=" * 64)
    print(f"  JUDGED TIER (paid)  —  arm={arm}  memo={memo_model}  judge={settings.judge_model}")
    if cross_judge_llm is not None:
        print(f"  cross-judge (~20% of obligations)  —  {cross_judge_model}")
    if score_grounded:
        print(
            f"  groundedness denominator: {'count-unresolvable' if count_unresolvable else 'skip'}"
        )
    else:
        print("  groundedness: NOT JUDGED (--no-groundedness) — generation + deterministic scoring")
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
        "grounded_unresolvable_counted": 0,  # of grounded_judged, how many were unresolvable "no"s
        "coverage_covered": 0,
        "coverage_total": 0,
        "obligations": 0,
        "cross_compared": 0,  # obligations the second-lab judge re-scored (§10 trap 4)
        "cross_agreed": 0,  # of those, how many matched the primary verdict
    }
    cross_disagreements: list[dict] = []
    currency_probes: list[dict] = []
    for case in arm_cases:
        # Tolerate a per-case LLM failure (e.g. a transient free-tier 429) — report it and keep going
        # rather than crashing the whole run on one bad call.
        try:
            memo = _produce_memo(core, case, arm, memo_llm)
            cite = score_citation_exists(memo, core.sections, case.id)
            grounded = (
                score_groundedness(
                    memo,
                    core.section_texts,
                    judge_llm,
                    case.id,
                    count_unresolvable_as_ungrounded=count_unresolvable,
                    cross_judge_llm=cross_judge_llm,
                )
                if score_grounded
                # D1: generation + deterministic scoring only. An all-zero outcome keeps every
                # downstream aggregate, print, and artifact shape identical rather than threading
                # None through them — and judged=0 reads honestly as "not judged" beside the
                # judged-N denominators (§7.3), which is exactly what happened.
                else GroundednessOutcome(case_id=case.id, judged=0, grounded_yes=0)
            )
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
        agg["grounded_unresolvable_counted"] += grounded.unresolvable_counted
        agg["coverage_covered"] += coverage.covered
        agg["coverage_total"] += coverage.total
        agg["obligations"] += sum(len(f.obligations) for f in memo.per_law)
        agg["cross_compared"] += grounded.cross_compared
        agg["cross_agreed"] += grounded.cross_agreed
        cross_disagreements += [
            {"case_id": case.id, "citation": c, "primary": p, "secondary": s}
            for (c, p, s) in grounded.cross_disagreements
        ]
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
    denom_note = (
        f"  ({agg['grounded_unresolvable_counted']} unresolvable counted as not-grounded)"
        if count_unresolvable and agg["grounded_unresolvable_counted"]
        else ""
    )
    print(f"    grounded(yes):   {agg['grounded_yes']}/{agg['grounded_judged']}{denom_note}")
    print(f"    coverage:        {agg['coverage_covered']}/{agg['coverage_total']}")
    print(f"    obligations:     {agg['obligations']} total")
    if currency_probes:
        flagged = sum(1 for p in currency_probes if p["stale"])
        print(f"    currency probes: {flagged}/{len(currency_probes)} stale-flagged (hand-verify)")
    if agg["cross_compared"]:
        # Report the ACTUAL sampled fraction (compared / total obligations) so no one has to trust a
        # "~20%" label — the sample is the lead obligation of each case plus every stride-th after, so
        # small memos are covered case-by-case rather than the sample clustering in the largest ones.
        print(
            f"    cross-judge:     {agg['cross_agreed']}/{agg['cross_compared']} agree "
            f"with {cross_judge_model}  "
            f"({agg['cross_compared']} of {agg['obligations']} obligations sampled"
            + (f", {len(cross_disagreements)} split)" if cross_disagreements else ")")
        )
    print("-" * 64)

    print(f"\n  memos written to {memo_dir}  (one .html per case — open them, not just the scores)")
    # Self-report spend so a run never depends on a captured tee log (obs tracks the running total).
    totals = cost_summary()
    unpriced = int(totals.get("unknown_rate_calls", 0))
    print(
        f"\n  run cost:  ${totals['cost_usd']:.4f}"
        f"{' (FLOOR — see warning below)' if unpriced else ''}  "
        f"({totals['llm_calls']} LLM calls, "
        f"{totals['input_tokens']:,} in / {totals['output_tokens']:,} out tokens)"
    )
    if unpriced:
        # A model missing from pricing.RATES books $0.00 per call, so an unpriced run looks free.
        # Loud, because §12 makes this number the provenance record for the whole benchmark.
        print(
            f"  WARNING: {unpriced} of {totals['llm_calls']} calls used a model with NO rate in "
            f"core/pricing.py — the cost above is a FLOOR, not the bill. Add the model id (in the "
            f"exact form the provider reports it) before trusting this figure."
        )

    # Persist the arm's aggregate + currency probes so the paid numbers are reproducible in the repo
    # (§3.3 — the full selection and every raw output live in the repo), arm-tagged so arms don't
    # collide. The per-case memo HTML is already on disk; this is the machine-readable scorecard.
    scorecard = RESULTS_DIR / f"judged-{stamp}-{arm}.json"
    scorecard.write_text(
        json.dumps(
            {
                "arm": arm,
                "run_stamp": stamp,
                "stub_dry_run": stub_dry_run,
                "provenance": _run_provenance(core),
                "memo_model": memo_model,
                "judge_model": settings.judge_model,
                "groundedness_scored": score_grounded,
                "groundedness_denominator": (
                    ("count-unresolvable" if count_unresolvable else "skip")
                    if score_grounded
                    else None
                ),
                "cross_judge_model": cross_judge_model,
                "cases": [c.id for c in arm_cases],
                "cases_scored": len(arm_cases) - errors,
                "errors": errors,
                "aggregate": agg,
                "cross_disagreements": cross_disagreements,
                "currency_probes": currency_probes,
                "cost_usd": totals["cost_usd"],
                # Nonzero => cost_usd is a floor, not the bill. Persisted so a scorecard can never
                # be read later as an authoritative $0.00 (the 2026-07-20 smoke-test failure).
                "unknown_rate_calls": unpriced,
                "input_tokens": totals["input_tokens"],
                "output_tokens": totals["output_tokens"],
            },
            indent=2,
        )
    )
    # Prefer a repo-relative path for readability, but never let a cosmetic print crash a run that has
    # already written its scorecard (e.g. RESULTS_DIR pointed outside cwd).
    try:
        shown = scorecard.relative_to(Path.cwd())
    except ValueError:
        shown = scorecard
    print(f"  wrote {shown}\n")


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
        help="judged-tier memo producer: patchwork (production) | baseline-open | baseline-primed | "
        "grounded-single (the D4 ablation: production corpus + gate, one cheap single-pass call)",
    )
    parser.add_argument(
        "--baseline-model",
        default=None,
        help="model id for the baseline and ablation arms (e.g. openai/gpt-5.6-sol, "
        "deepseek/deepseek-v4-pro); ignored for --arm patchwork",
    )
    parser.add_argument(
        "--cases",
        default=None,
        help="restrict judged tier to a case set: 'phase14' (the 13-case publish set) or a "
        "comma-separated list of gold case ids",
    )
    parser.add_argument(
        "--cross-judge",
        action="store_true",
        help="also re-judge ~20%% of obligations with a second-lab judge and report inter-judge "
        "agreement (§10 trap 4); paid",
    )
    parser.add_argument(
        "--cross-judge-model",
        default=_DEFAULT_CROSS_JUDGE_MODEL,
        help=f"second judge model for --cross-judge (default {_DEFAULT_CROSS_JUDGE_MODEL})",
    )
    parser.add_argument(
        "--no-groundedness",
        action="store_true",
        help="generate memos and score citations/coverage/currency WITHOUT the paid Opus groundedness "
        "judge (~2/3 of a judged case). This is the D1 'core run': the judged tier stays built and "
        "is a separate, later spend decision made with real data in hand",
    )
    parser.add_argument(
        "--stub-judged",
        action="store_true",
        help="run the judged tier end-to-end on StubLLM at $0 (offline dry run; requires "
        "LLM_PROVIDER=stub). Exercises arm dispatch, scoring, artifacts, provenance before a paid run",
    )
    args = parser.parse_args()

    # The cross-judge re-scores the primary judge's verdicts, so it is meaningless with no primary
    # judge — and it would silently spend on a second judge during a run asked to skip judging.
    if args.no_groundedness and args.cross_judge:
        parser.error("--no-groundedness and --cross-judge are mutually exclusive")

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

    if args.judge or args.stub_judged or settings.eval_use_judge:
        run_judged(
            core,
            cases,
            arm=args.arm,
            baseline_model=args.baseline_model,
            case_ids=case_ids,
            limit=args.limit,
            offset=args.offset,
            stamp=stamp,
            cross_judge_model=args.cross_judge_model if args.cross_judge else None,
            stub_dry_run=args.stub_judged,
            score_grounded=not args.no_groundedness,
        )

    if args.strict and scope_correct < scope_total:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
