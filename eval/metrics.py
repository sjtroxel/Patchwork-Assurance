"""Deterministic eval metrics — Tier A: free, offline, no API key.

Scope accuracy and retrieval hit-rate. The judged metrics (citation groundedness, obligation
coverage) are Tier B, wired later behind a flag (phase-6 IMPLEMENTATION §6) because they spend
API tokens.
"""

import re
from dataclasses import dataclass

from eval.harness import Core
from eval.loader import GoldCase, RetrievalQueryCase
from patchwork_assurance.core.contracts import ComplianceMemo
from patchwork_assurance.core.grounding import locate_section
from patchwork_assurance.core.memo import (  # production query builder + key-obligation pin
    _focus,
    _pin_key_obligations,
)
from patchwork_assurance.core.retrieval import RetrievalFilters
from patchwork_assurance.core.scope import applicable_laws

_IN_SCOPE = ("yes", "uncertain")

# We import memo._focus on purpose: the retrieval metric must query with the EXACT string the
# memo path uses, or it would measure a different path than production (the whole point of the
# harness). _focus is module-private today; promoting it to a public helper is a clean future tidy.


@dataclass
class ScopeOutcome:
    case_id: str
    got: dict[str, str]  # law_id -> verdict the screen produced
    expected: dict[str, str]
    correct: int
    total: int


def score_scope(case: GoldCase, core: Core) -> ScopeOutcome:
    """Run the real scope screen and compare every per-law verdict to the gold answer."""
    got = {r.law_id: r.in_scope for r in applicable_laws(case.situation, core.laws)}
    expected = case.expect.scope
    correct = sum(1 for law_id, want in expected.items() if got.get(law_id) == want)
    return ScopeOutcome(case.id, got, expected, correct, len(expected))


@dataclass
class RetrievalOutcome:
    case_id: str
    want: list[str]
    hit: list[str]
    missed: list[str]
    recall: float


def score_retrieval(
    case: GoldCase, core: Core, k: int, mode: str = "filtered", pin: bool = True
) -> RetrievalOutcome | None:
    """Retrieve per in-scope law (mirroring memo.generate_memo's per-law filtered retrieve) and
    check which gold grounding sections were surfaced in the top-k. Routes through the Phase 8
    query() entry point so the sweep measures the configured `mode` (semantic | filtered | hybrid).
    Returns None for out-of-scope cases (no grounding to score).

    `pin` mirrors production's key-obligation pin (memo.retrieve_per_law): the memo guarantees each
    in-scope law's curated `key_obligations` sections are grounded, so the main eval must too or it
    measures a different path than production (rag.md). The knob sweep passes `pin=False` to measure
    the raw semantic layer the pin backstops (otherwise every embedding config scores ~100% on the
    pinned sections and the comparison is blind)."""
    want = case.expect.grounding_sections
    if not want:
        return None
    query = _focus(case.situation)
    laws_by_id = {law.law_id: law for law in core.laws}
    retrieved: set[str] = set()
    for result in applicable_laws(case.situation, core.laws):
        if result.in_scope in _IN_SCOPE:
            chunks = core.retriever.query(
                # Mirror the memo: filter per law_id, since a jurisdiction can hold >1 law (CA).
                query,
                RetrievalFilters(law_id=result.law_id),
                k=k,
                mode=mode,
            )
            if pin and result.law_id in laws_by_id:
                _pin_key_obligations(core.retriever, laws_by_id[result.law_id], query, chunks)
            retrieved |= {c.section_number for c in chunks}
    hit = [s for s in want if s in retrieved]
    missed = [s for s in want if s not in retrieved]
    return RetrievalOutcome(case.id, want, hit, missed, len(hit) / len(want))


def score_query_retrieval(
    case: RetrievalQueryCase, core: Core, k: int, mode: str = "filtered"
) -> RetrievalOutcome:
    """Recall@k for an exact-term / citation query (Phase 8 §7): query the corpus with the case's raw
    free-text string (optionally jurisdiction-filtered) through the same query() entry point, and check
    which expected sections surfaced. This is where lexical/hybrid/routed can beat semantic — a bare
    section number is a strong lexical signal and a weak semantic one."""
    want = case.grounding_sections
    filters = RetrievalFilters(jurisdiction=case.jurisdiction) if case.jurisdiction else None
    chunks = core.retriever.query(case.query, filters, k=k, mode=mode)
    retrieved = {c.section_number for c in chunks}
    hit = [s for s in want if s in retrieved]
    missed = [s for s in want if s not in retrieved]
    return RetrievalOutcome(case.id, want, hit, missed, len(hit) / len(want) if want else 0.0)


# --- citation-exists (Tier B: deterministic check, but needs a real generated memo) ---
# The cheap guard against the worst failure for a compliance tool: citing a statute section that
# does not exist (phase-6 IMPLEMENTATION §5). Free to build/test now; measured on a real memo later.


@dataclass
class CitationOutcome:
    case_id: str
    total: int
    valid: int
    invalid: list[str]  # cited strings that don't resolve to a real corpus section


def score_citation_exists(
    memo: ComplianceMemo, sections: dict[str, set[str]], case_id: str = ""
) -> CitationOutcome:
    """Every section the memo's obligations cite must resolve to a real section in the corpus."""
    cited = [ob.citation for finding in memo.per_law for ob in finding.obligations]
    invalid = [c for c in cited if locate_section(c, sections) is None]
    return CitationOutcome(case_id, len(cited), len(cited) - len(invalid), invalid)


# --- obligation coverage (deterministic, fuzzy: free; needs a real generated memo to measure) ---
# Are the gold obligations present in the memo (paraphrase allowed)? A weak text-overlap proxy; a
# judge-based coverage check is the upgrade (phase-6 IMPLEMENTATION §6) when the metric outgrows it.
#
# History: the first cut used difflib.SequenceMatcher char-ratio >= 0.50 against the single best
# memo obligation. That is mathematically unreachable for a paraphrase of a long (300+ char) gold
# sentence — the 2026-06-29 judged run scored 1/37 (2.7%) on memos that were actually well-covered.
# Replaced 2026-06-29 with gold-content-word recall against the POOLED memo text: a gold obligation
# is "covered" if >= `threshold` of its content words appear anywhere across the union of the memo's
# obligation prose AND citation strings. Pooling matters because one terse gold sentence often maps
# to several memo obligations; folding in citations matters because some gold entries carry the duty
# as a bare section number (e.g. "6-1-1704", "11 CCR 7220") the memo keeps in its citation field.
# This is still a weak proxy — groundedness (the Opus judge) remains the real quality signal — and it
# under-counts the few gold entries written as cross-references ("Same ... as case X").

# Genuine English stopwords plus a couple of cross-reference connectives that carry no obligation
# content ("same ... as case ..."), so they don't inflate a shorthand gold entry's recall.
_STOP = frozenset(
    "a an the of to in on for and or by with as is are be been that this it its which may must "
    "shall not no any all each per their before use used uses using under over into out from at "
    "than then so such these those there here other others incl including include includes etc "
    "same case duties".split()
)


def _content_words(text: str) -> set[str]:
    """Lowercased alphanumeric tokens (len > 2) that aren't stopwords — the comparable content."""
    return {w for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2 and w not in _STOP}


@dataclass
class CoverageOutcome:
    case_id: str
    total: int
    covered: int
    missed: list[str]  # gold obligations whose content words aren't sufficiently present


def score_coverage(
    memo: ComplianceMemo, gold_obligations: list[str], threshold: float = 0.6, case_id: str = ""
) -> CoverageOutcome:
    """For each gold obligation, do >= `threshold` of its content words appear in the memo's pooled
    obligation text + citations? Word-recall tolerates paraphrase and many-to-one mapping; it is a
    weak proxy and the judge tier is the real coverage signal."""
    pool: set[str] = set()
    for finding in memo.per_law:
        for ob in finding.obligations:
            pool |= _content_words(ob.text)
            pool |= _content_words(ob.citation)
    missed = []
    for gold in gold_obligations:
        gold_words = _content_words(gold)
        recall = len(gold_words & pool) / len(gold_words) if gold_words else 0.0
        if recall < threshold:
            missed.append(gold)
    return CoverageOutcome(
        case_id, len(gold_obligations), len(gold_obligations) - len(missed), missed
    )
