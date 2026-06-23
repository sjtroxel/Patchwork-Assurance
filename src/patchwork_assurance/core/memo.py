from patchwork_assurance.core.contracts import (
    ComplianceMemo,
    DeadlineItem,
    Msg,
    ScopeResult,
    Situation,
)
from patchwork_assurance.core.corpus.metadata import LawMetadata
from patchwork_assurance.core.prompts import MEMO_SYSTEM, render_memo_user
from patchwork_assurance.core.retrieval import RetrievalFilters

_IN_SCOPE = ("yes", "uncertain")

# How many statute chunks to retrieve per in-scope law for the memo. Raised 5 -> 8 after the
# Phase 6 eval: retrieval recall@5 was 68% (CO 6-1-1705, the human-review right, ranked 6th-12th
# for the deployer query), recall@8 ~95%. The eval reads THIS constant so it always measures the
# real memo depth. A deeper fix (hybrid retrieval) is Phase 8; the facts card already backstops it.
MEMO_RETRIEVAL_K = 8
# Coverage beyond consequential decisions about people (e.g. CT's AI-companion / generative-AI /
# frontier-model provisions) — surfaced as a note, not a form gate (Phase 4.6, Fork D).
_PRODUCT_DOMAINS = {
    "ai_companion",
    "generative_ai_provenance",
    "frontier_models",
    "online_safety_minors",
}


def generate_memo(
    situation: Situation,
    scope: list[ScopeResult],
    retriever,
    llm,
    laws: list[LawMetadata] | None = None,
) -> ComplianceMemo:
    laws_by_id = {law.law_id: law for law in (laws or [])}
    chunks = []
    for s in scope:
        if s.in_scope in _IN_SCOPE:
            chunks += retriever.retrieve(
                query=_focus(situation),
                filters=RetrievalFilters(jurisdiction=s.jurisdiction),
                k=MEMO_RETRIEVAL_K,
            )
    user = render_memo_user(situation, scope, chunks, list(laws_by_id.values()))
    memo = llm.complete_structured(MEMO_SYSTEM, [Msg(role="user", content=user)], ComplianceMemo)

    # Deadlines and orientation are facts/templates, not LLM guesses — set them deterministically so
    # CT's staggered dates and the not-legal-advice-shaped "next steps" stay correct and controlled.
    if laws_by_id:
        memo.deadline_checklist = _deadlines(scope, laws_by_id)
    memo.next_steps = _next_steps(situation, scope, laws_by_id)
    return memo


def _focus(situation: Situation) -> str:
    return (
        f"obligations for {'/'.join(situation.roles) or 'a business'} using AI in "
        f"{'/'.join(situation.decision_domains) or 'consequential'} decisions"
    )


def _deadlines(scope: list[ScopeResult], laws_by_id: dict[str, LawMetadata]) -> list[DeadlineItem]:
    """Every effective date for each in-scope law, straight from the metadata, sorted — so the
    operative date (e.g. CT's AERDT deployer-notice duty on 2027-10-01) surfaces with its staggered
    siblings instead of the LLM guessing or collapsing them."""
    items: list[DeadlineItem] = []
    for s in scope:
        if s.in_scope not in _IN_SCOPE:
            continue
        law = laws_by_id.get(s.law_id)
        if not law:
            continue
        for ed in law.effective_dates:
            items.append(
                DeadlineItem(date=ed.date.isoformat(), what=ed.applies_to, law=s.short_name)
            )
    items.sort(key=lambda d: d.date)
    return items


def _next_steps(
    situation: Situation, scope: list[ScopeResult], laws_by_id: dict[str, LawMetadata]
) -> list[str]:
    """A condensed, hedged orientation checklist (Phase 4.6, Fork F). Templated, not LLM-generated,
    so this advice-shaped output stays controlled and consistent. Educational, not a compliance plan."""
    in_scope = [s for s in scope if s.in_scope in _IN_SCOPE]
    if not in_scope:
        return [
            "Nothing here appears to reach you on what you described. If your situation changes (new "
            "states, new AI tools, new decision types), re-run this, and consult a licensed attorney "
            "before relying on any conclusion."
        ]

    steps = []
    if situation.ai_use == "unsure":
        steps.append(
            "Inventory the AI and automated tools you use: list every tool that scores, ranks, "
            "screens, or recommends people. You can't address tools you haven't identified."
        )
    steps += [
        "Note which tools touch which state, and calendar the deadlines below.",
        "Draft a plain-language notice for the people affected by these decisions (one template can "
        "cover multiple states, with state-specific additions).",
        "Set a simple process for human review of, and disclosure about, AI-assisted decisions, and "
        "keep records.",
        "Take this summary to a licensed attorney in the relevant state before making compliance "
        "decisions. It is a starting point, not a compliance plan.",
    ]

    # Fork D: flag coverage beyond the consequential decisions the form captures.
    selected = set(situation.decision_domains)
    for s in in_scope:
        law = laws_by_id.get(s.law_id)
        if not law:
            continue
        extra = (set(law.scope_domains) & _PRODUCT_DOMAINS) - selected
        if extra:
            pretty = ", ".join(sorted(d.replace("_", " ") for d in extra))
            steps.append(
                f"Note: {s.short_name} also regulates {pretty}. If your business builds or operates "
                "those, consult counsel about additional obligations beyond this summary."
            )
    return steps
