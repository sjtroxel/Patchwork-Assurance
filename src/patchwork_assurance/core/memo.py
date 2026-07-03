from collections.abc import Callable
from datetime import date

from patchwork_assurance.config import settings
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
# real memo depth. The remaining gap (a law whose material rule is worded unlike the generic focus
# query — Texas TRAIGA's § 552.056 ranked ~19th under ~34 sandbox/council sections) is closed by the
# key-obligation pin in retrieve_per_law, not by raising k: recall@8 is now 100% (2026-07-03).
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
    *,
    on_event: Callable | None = None,
) -> ComplianceMemo:
    """The one public entry point (the keystone: api/, ui/, eval/, mcp/ all call this name). Phase 12
    splits the middle GENERATION step behind a config flag; the deterministic overlays and the output
    contract are unchanged either way, so both paths emit the same ComplianceMemo.

    `on_event` is an optional progress hook (an AgentEvent callback) the streaming surface
    (`/analyze/stream`, Phase 12 §9) drives the live panel with. Only the multi_agent pipeline emits
    events; the single path ignores it. None everywhere else (eval/MCP/CLI/the non-streaming /analyze)."""
    laws_by_id = {law.law_id: law for law in (laws or [])}
    if settings.memo_pipeline == "multi_agent":
        memo = _generate_multi_agent(
            situation, scope, retriever, llm, laws_by_id, on_event=on_event
        )
    else:
        memo = _generate_single(situation, scope, retriever, llm, laws_by_id)
    _apply_deterministic_overlays(memo, situation, scope, laws_by_id)
    return memo


def retrieve_per_law(
    situation: Situation,
    scope: list[ScopeResult],
    retriever,
    laws_by_id: dict[str, LawMetadata] | None = None,
) -> dict[str, list]:
    """Per-law chunk buckets for the in-scope laws (keyed by law_id), using the same focus query,
    RetrievalFilters(law_id=...), and MEMO_RETRIEVAL_K everywhere. Filter by law_id, not jurisdiction:
    a jurisdiction can hold more than one law (e.g. California's FEHA ADS + CCPA ADMT regs), and each
    law's section must be grounded only in its own statute text. Shared by _generate_single (which
    merges the buckets into one prompt) and the Phase 12 analyst fan-out (which keeps them separate —
    that separation IS the cross-law isolation).

    Semantic top-k alone is not enough for laws with many sections whose material rule is worded
    unlike the generic focus query: Texas TRAIGA frames its one private-sector rule as "unlawful
    discrimination" (§ 552.056) and buries it under ~30 sandbox/council sections, so it ranks past
    k=8. Defense: **pin every in-scope law's own curated `key_obligations` sections** (the
    human-authored source of truth) into its bucket, then let semantic top-k fill the rest. Generic
    over N statutes — it reads each law's metadata, no per-jurisdiction branch. `laws_by_id` is
    optional only so older/tests callers still work; production always passes it."""
    laws_by_id = laws_by_id or {}
    query = _focus(situation)
    buckets: dict[str, list] = {}
    for s in scope:
        if s.in_scope not in _IN_SCOPE:
            continue
        chunks = retriever.retrieve(
            query=query, filters=RetrievalFilters(law_id=s.law_id), k=MEMO_RETRIEVAL_K
        )
        law = laws_by_id.get(s.law_id)
        if law:
            _pin_key_obligations(retriever, law, query, chunks)
        buckets[s.law_id] = chunks
    return buckets


def _pin_key_obligations(retriever, law: LawMetadata, query: str, chunks: list) -> None:
    """Ensure each of `law`'s curated key-obligation sections is present in `chunks`, fetching any
    that semantic top-k missed. Mutates `chunks` in place (append), deduped by chunk_index. Section
    tokens are normalized out of the metadata's `key_obligations[].section` strings with the shared
    citation parser, so "Tex. Bus. & Com. Code § 552.056" and "775 ILCS 5/2-102(L)(1)" both resolve
    to the bare chunk section_number; non-citation entries (e.g. "IDHR rulemaking") yield nothing and
    are skipped."""
    have_sections = {c.section_number for c in chunks}
    have_indexes = {c.chunk_index for c in chunks}
    for token in _key_obligation_sections(law):
        if token in have_sections:
            continue
        pinned = retriever.retrieve(
            query=query,
            filters=RetrievalFilters(law_id=law.law_id, section_number=token),
            k=MEMO_RETRIEVAL_K,
        )
        for pc in pinned:
            if pc.chunk_index not in have_indexes:
                chunks.append(pc)
                have_indexes.add(pc.chunk_index)
                have_sections.add(pc.section_number)


def _key_obligation_sections(law: LawMetadata) -> list[str]:
    """The bare chunk-section tokens named by a law's key_obligations, order-preserving and deduped.
    Uses the shared `cited_sections` citation parser so it stays generic over each jurisdiction's
    citation format (the same parser the grounding guard uses)."""
    from patchwork_assurance.core.grounding import cited_sections

    out: list[str] = []
    for obl in law.key_obligations:
        for token in cited_sections(obl.section):
            if token not in out:
                out.append(token)
    return out


def _generate_single(
    situation: Situation,
    scope: list[ScopeResult],
    retriever,
    llm,
    laws_by_id: dict[str, LawMetadata],
) -> ComplianceMemo:
    """Today's path: retrieve every in-scope law's chunks into one list and generate the whole memo
    in a single complete_structured call."""
    buckets = retrieve_per_law(situation, scope, retriever, laws_by_id)
    chunks = []
    for s in scope:
        if s.in_scope in _IN_SCOPE:
            chunks += buckets[s.law_id]
    user = render_memo_user(situation, scope, chunks, list(laws_by_id.values()))
    return llm.complete_structured(MEMO_SYSTEM, [Msg(role="user", content=user)], ComplianceMemo)


def _generate_multi_agent(
    situation: Situation,
    scope: list[ScopeResult],
    retriever,
    llm,
    laws_by_id: dict[str, LawMetadata],
    *,
    on_event: Callable | None = None,
) -> ComplianceMemo:
    """Phase 12: per-law analyst fan-out + grounding/hedge reviewer. The passed `llm` is the analyst
    model (Sonnet); the reviewer model is built from settings internally so the two-model pipeline
    needs no new caller argument. Imports are LOCAL to break the memo<->orchestrator cycle (the
    orchestrator imports retrieve_per_law from this module at load time)."""
    from pathlib import Path

    from patchwork_assurance.core.agents.orchestrator import run_multi_agent_memo
    from patchwork_assurance.core.grounding import corpus_section_texts
    from patchwork_assurance.core.llm import build_llm

    analyst_model = settings.analyst_model or settings.memo_model
    reviewer_model = settings.reviewer_model or settings.judge_model
    reviewer_llm = build_llm(settings, reviewer_model)
    # Deterministic disk read (no embeddings, no store) — the ground truth the reviewer judges against.
    section_texts = corpus_section_texts(Path(settings.corpus_path))
    return run_multi_agent_memo(
        situation,
        scope,
        retriever,
        llm,
        reviewer_llm,
        list(laws_by_id.values()),
        analyst_model=analyst_model,
        reviewer_model=reviewer_model,
        section_texts=section_texts,
        max_revisions=settings.reviewer_max_revisions,
        on_event=on_event,
    )


def _apply_deterministic_overlays(
    memo: ComplianceMemo,
    situation: Situation,
    scope: list[ScopeResult],
    laws_by_id: dict[str, LawMetadata],
) -> None:
    """The controlled facts/advice scaffolding both pipelines share. Deadlines, the dated stamps, and
    orientation are facts/templates, not LLM guesses — set them deterministically so CT's staggered
    dates, the trustworthy "as of" stamp, and the not-legal-advice-shaped "next steps" stay correct
    and controlled (Phase 4.6, Phase 11). Byte-identical for single vs multi-agent (the DoD)."""
    memo.generated_on = date.today().isoformat()
    # The corpus's currency = the latest statute-retrieval date across the laws considered. Set
    # unconditionally (None when no metadata) so the stamp is always fully determined here, never
    # left to a value the LLM emitted. getattr-guarded so test fixtures built with model_construct
    # (no retrieved_on) degrade to None.
    retrieved = [
        law.retrieved_on for law in laws_by_id.values() if getattr(law, "retrieved_on", None)
    ]
    memo.corpus_as_of = max(retrieved).isoformat() if retrieved else None
    if laws_by_id:
        memo.deadline_checklist = _deadlines(scope, laws_by_id)
    memo.next_steps = _next_steps(situation, scope, laws_by_id)


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
