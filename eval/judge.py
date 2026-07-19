"""LLM-as-judge metrics — Tier B. Spends API tokens; only runs under --judge / `make eval-judge`.

The reusable judge primitives (`JUDGE_SYSTEM`, `JudgeVerdict`, `judge_groundedness`) moved to
`core.judge` in Phase 12 so the live reviewer agent can call them too (core/ can't import eval/).
This module keeps the eval-only aggregator, `score_groundedness`, and re-imports the primitives.

Groundedness is the legal-integrity metric: the judge sees an obligation claim plus the statute
text it cites, and decides whether the claim is supported by THAT text — the check that catches a
plausible-sounding but hallucinated obligation, the worst failure for a compliance tool.
"""

from dataclasses import dataclass, field

from patchwork_assurance.core.contracts import ComplianceMemo
from patchwork_assurance.core.grounding import locate_section
from patchwork_assurance.core.judge import (  # noqa: F401 — re-exported for existing importers/tests
    JUDGE_SYSTEM,
    JudgeVerdict,
    judge_groundedness,
)


@dataclass
class GroundednessOutcome:
    case_id: str
    judged: int  # obligations whose cited section text we could locate and judge
    grounded_yes: int
    verdicts: list[tuple[str, str]] = field(default_factory=list)  # (citation, grounded)
    unsupported: list[str] = field(default_factory=list)
    # Phase 14 §10 / decision #2: under `count_unresolvable_as_ungrounded` (baseline arms) an
    # unresolvable citation lands in `judged` as a "no" instead of being skipped, so a model can't
    # delete its worst (fabricated / repealed-section) output from its own denominator. Counted
    # separately so the reported number stays transparent about how many of the "no"s came from here.
    unresolvable_counted: int = 0
    # Phase 14 §10 trap 4: a deterministic ~20% subset of the LOCATABLE obligations is re-judged by a
    # second-lab judge to test the Opus-judges-Opus self-preference concern. compared/agreed are the
    # inter-judge agreement denominator/numerator; disagreements list the exact splits for a glance.
    cross_compared: int = 0
    cross_agreed: int = 0
    cross_disagreements: list[tuple[str, str, str]] = field(  # (citation, primary, secondary)
        default_factory=list
    )


def score_groundedness(
    memo: ComplianceMemo,
    section_texts: dict[str, dict[str, str]],
    llm,
    case_id: str = "",
    *,
    count_unresolvable_as_ungrounded: bool = False,
    cross_judge_llm=None,
    cross_judge_stride: int = 5,
) -> GroundednessOutcome:
    """Judge every memo obligation against the text of the section it cites.

    Default (the patchwork arm, byte-identical to pre-Phase-14): obligations whose citation doesn't
    resolve to a real section are skipped here — citation-exists already flags those, and groundedness
    only judges claims we can pair with real statute text.

    `count_unresolvable_as_ungrounded=True` (baseline arms, decision #2): an unresolvable citation is
    instead counted as a not-grounded obligation. The honest denominator for a raw model, whose worst
    currency failures are exactly the citations that don't resolve — skipping them would let it post a
    groundedness number built only on its corpus-matching subset (§10).

    `cross_judge_llm` (§10 trap 4): when given, a deterministic every-`cross_judge_stride`-th locatable
    obligation is ALSO judged by that second model and compared to the primary verdict. Re-uses the
    primary verdict already computed, so the second judge is the only extra call. Unresolvable cites are
    never cross-judged — there is no statute text to hand a judge."""
    sections = {jurisdiction: set(texts) for jurisdiction, texts in section_texts.items()}
    out = GroundednessOutcome(case_id, judged=0, grounded_yes=0)
    located_index = 0  # counts only locatable obligations, so the ~20% stride is stable across arms
    for finding in memo.per_law:
        for obligation in finding.obligations:
            located = locate_section(obligation.citation, sections)
            if located is None:
                if count_unresolvable_as_ungrounded:
                    out.judged += 1
                    out.unresolvable_counted += 1
                    out.verdicts.append((obligation.citation, "no"))
                continue
            jurisdiction, section = located
            statute_text = section_texts[jurisdiction][section]
            verdict = judge_groundedness(obligation.text, statute_text, llm)
            out.judged += 1
            if verdict.grounded == "yes":
                out.grounded_yes += 1
            out.verdicts.append((obligation.citation, verdict.grounded))
            out.unsupported += verdict.unsupported_claims
            if cross_judge_llm is not None and located_index % cross_judge_stride == 0:
                second = judge_groundedness(obligation.text, statute_text, cross_judge_llm)
                out.cross_compared += 1
                if second.grounded == verdict.grounded:
                    out.cross_agreed += 1
                else:
                    out.cross_disagreements.append(
                        (obligation.citation, verdict.grounded, second.grounded)
                    )
            located_index += 1
    return out
