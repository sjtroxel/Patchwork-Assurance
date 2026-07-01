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


def score_groundedness(
    memo: ComplianceMemo, section_texts: dict[str, dict[str, str]], llm, case_id: str = ""
) -> GroundednessOutcome:
    """Judge every memo obligation against the text of the section it cites. Obligations whose
    citation doesn't resolve to a real section are skipped here (citation-exists already flags
    those) — groundedness only judges claims we can pair with real statute text."""
    sections = {jurisdiction: set(texts) for jurisdiction, texts in section_texts.items()}
    out = GroundednessOutcome(case_id, judged=0, grounded_yes=0)
    for finding in memo.per_law:
        for obligation in finding.obligations:
            located = locate_section(obligation.citation, sections)
            if located is None:
                continue
            jurisdiction, section = located
            verdict = judge_groundedness(obligation.text, section_texts[jurisdiction][section], llm)
            out.judged += 1
            if verdict.grounded == "yes":
                out.grounded_yes += 1
            out.verdicts.append((obligation.citation, verdict.grounded))
            out.unsupported += verdict.unsupported_claims
    return out
