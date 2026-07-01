"""The reviewer agent — the J.D. edge as an agent (Phase 12 §6).

It does NOT invent new code: it is the Phase 6 groundedness judge promoted from offline-eval into the
live pipeline, gated in front of the Phase 7 deterministic citation guard and the legal-language guard.
For each obligation, in order (free checks first, LLM only on what survives):

  1. Deterministic citation pre-filter (FREE) — a citation that resolves to no real section is dropped
     without spending a token (exactly score_groundedness's skip logic, used here to GATE).
  2. Groundedness judge (LLM) — is the claim supported by ITS cited statute text? no -> drop,
     partial -> flag (or a bounded revise), yes -> keep.
  3. Language / hedge guard — drop anything that guarantees / over-claims (or revise it first).
  4. Bounded revise-loop — at most reviewer_max_revisions (default 1). No infinite debate.

It also writes the natural-language executive summary. Framing (keep crisp in any writeup): the reviewer
makes the *educational* memo more reliably grounded and hedged. It is NOT legal advice and NOT the
Phase 9 human-in-the-loop corpus gate.
"""

from patchwork_assurance.core.agents.trace import AgentEvent
from patchwork_assurance.core.contracts import LawFinding, MemoObligation, Msg, Situation
from patchwork_assurance.core.grounding import locate_section
from patchwork_assurance.core.judge import judge_groundedness
from patchwork_assurance.core.language import has_prohibited_language
from patchwork_assurance.core.prompts import (
    REVIEWER_SUMMARY_SYSTEM,
    REVISER_SYSTEM,
    render_reviser_user,
    render_summary_user,
)


def review_findings(
    findings: list[LawFinding],
    situation: Situation | None,
    section_texts: dict[str, dict[str, str]],
    reviewer_llm,
    reviewer_model: str,
    *,
    max_revisions: int = 1,
    on_event=None,
) -> tuple[list[LawFinding], str, list[AgentEvent]]:
    """Verify each obligation against its cited statute text; drop/flag/revise; write the summary.
    Returns (reviewed findings, summary, events). `summary` is "" if the reviewer's summary trips the
    language guard, so assembly falls back to the deterministic executive_summary (Phase 11)."""
    sections = {jur: set(texts) for jur, texts in section_texts.items()}
    events: list[AgentEvent] = []
    reviewed: list[LawFinding] = []

    for finding in findings:
        kept: list[MemoObligation] = []
        for ob in finding.obligations:
            result, kind, detail = _review_obligation(
                ob, sections, section_texts, reviewer_llm, max_revisions
            )
            ev = AgentEvent(
                kind="review_verdict",
                model=reviewer_model,
                law_id=finding.law_id,
                detail=f"{kind} ({detail}): {ob.citation}" if detail else f"{kind}: {ob.citation}",
            )
            events.append(ev)
            if on_event:
                on_event(ev)
            if result is not None:
                kept.append(result)
        reviewed.append(finding.model_copy(update={"obligations": kept}))

    summary = _write_summary(reviewed, situation, reviewer_llm)
    ev = AgentEvent(kind="review_summary", model=reviewer_model, detail="summary written")
    events.append(ev)
    if on_event:
        on_event(ev)
    return reviewed, summary, events


def _review_obligation(
    ob: MemoObligation,
    sections: dict[str, set[str]],
    section_texts: dict[str, dict[str, str]],
    llm,
    max_revisions: int,
) -> tuple[MemoObligation | None, str, str]:
    """Return (kept obligation or None, verdict-kind, detail). verdict-kind in
    {"grounded", "flagged", "dropped"}."""
    # 1. FREE deterministic pre-filter — a fabricated citation is dropped before any token is spent.
    located = locate_section(ob.citation, sections)
    if located is None:
        return None, "dropped", "fabricated citation"
    jurisdiction, section = located
    statute = section_texts[jurisdiction][section]

    # 2. Groundedness judge (LLM), then 4. a single bounded revise if partial or over-claiming.
    verdict = judge_groundedness(ob.text, statute, llm).grounded
    revised = False
    if max_revisions > 0 and (verdict == "partial" or has_prohibited_language(ob.text)):
        ob = _revise(ob, statute, llm)
        verdict = judge_groundedness(ob.text, statute, llm).grounded
        revised = True

    if verdict == "no":
        return (
            None,
            "dropped",
            "revised, still unsupported" if revised else "unsupported by cited text",
        )
    # 3. Language / hedge guard — if a revise didn't (or couldn't) fix over-claiming, drop it.
    if has_prohibited_language(ob.text):
        return None, "dropped", "over-claiming language"

    kind = "grounded" if verdict == "yes" else "flagged"
    return ob, kind, "revised" if revised else ""


def _revise(ob: MemoObligation, statute: str, llm) -> MemoObligation:
    """One bounded revise: re-ask the reviewer to hedge/ground the obligation against its cited text.
    The citation is kept (it already resolved) — the model rewrites only the prose."""
    fixed = llm.complete_structured(
        REVISER_SYSTEM,
        [Msg(role="user", content=render_reviser_user(ob.text, statute))],
        MemoObligation,
    )
    fixed.citation = ob.citation
    return fixed


def _write_summary(findings: list[LawFinding], situation: Situation | None, llm) -> str:
    """The reviewer's NL executive summary. Falls back to "" (assembly then uses the deterministic
    Phase 11 line) if the generated text trips the language guard — a belt-and-suspenders boundary."""
    summary = llm.complete(
        REVIEWER_SUMMARY_SYSTEM,
        [Msg(role="user", content=render_summary_user(findings, situation))],
    )
    return "" if has_prohibited_language(summary) else summary.strip()
