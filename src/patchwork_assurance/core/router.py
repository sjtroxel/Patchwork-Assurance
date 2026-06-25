"""Retrieval routing (Phase 8 §5) — pick the rung per query.

Two routers, deliberately ordered cheapest-first:

  - rules_route   — deterministic, zero tokens, fully unit-testable. Inspects the question for cheap
                    structural cues (a section number, a defined term, a factual pattern) and names a
                    chunk-retrieval mode. This is the production baseline that `Retriever.query(mode=
                    "routed")` dispatches through, and a legitimate winner at N=2 (plan §8).
  - agentic_route — the learning rep: the chat model is handed `search_corpus` / `query_metadata`
                    tools and *chooses* which to call (Anthropic-style tool-use loop, §6). It returns
                    the model's final grounded answer plus the ordered tool names it picked, so the
                    trace/eval can see the path. COST-BEARING (≥1 LLM round-trip; if it picks
                    query_metadata→text_to_sql that's two) and only as good as the model — free
                    OpenRouter models can't run it reliably, so its activation rides the same
                    funded/paid gate as the Phase 6 judged run. Built and offline-tested with StubLLM.

Everything stays in core/ (keystone invariant); nothing here imports api/ or ui/.
"""

import json
import re

from pydantic import BaseModel

from patchwork_assurance.core.contracts import Msg, RetrievedChunk, ToolRunResult

# --- rules router (deterministic baseline) ----------------------------------------------------------

# A statute section number (e.g. 6-1-1704) or the section sign — a citation/exact-term cue.
_CITATION = re.compile(r"\b\d+-\d+-\d+\b|§")
# A quoted phrase or one of the two laws' operative terms — also an exact-term cue (rag.md: do not
# harmonize "materially influence" (CO/ADMT) vs "substantial factor" (CT/AERDT)).
_DEFINED_TERM = re.compile(
    r"\"[^\"]+\"|\b(materially influence|substantial factor|ADMT|AERDT)\b", re.I
)
# A factual/metadata pattern — dates, cure period, enforcement, scope. These are what the structured
# path answers best; with query()'s chunk contract we route them to the lexical-weighted fused rung
# (the structured table proper is reached via the agentic router's query_metadata tool).
_FACTUAL = re.compile(
    r"\b(when|which laws?|what date|effective|deadline|cure period|enforce\w*|"
    r"penalt\w*|private right|who regulates)\b",
    re.I,
)


class Route(BaseModel):
    """The rules router's decision: a chunk-retrieval mode plus a short, query-text-free reason
    (safe to log — it names the cue class, never the user's words)."""

    mode: str  # semantic | filtered | hybrid
    reason: str


def rules_route(question: str) -> Route:
    q = question.strip()
    if _CITATION.search(q) or _DEFINED_TERM.search(q):
        return Route(mode="hybrid", reason="citation/defined-term -> lexical-weighted fusion")
    if _FACTUAL.search(q):
        return Route(mode="hybrid", reason="factual -> lexical-weighted fusion")
    return Route(mode="filtered", reason="conceptual -> filtered semantic")


# --- agentic router (the learning rep) --------------------------------------------------------------

_AGENTIC_SYSTEM = (
    "You answer questions about US state AI-regulation statutes (Colorado SB 26-189, Connecticut SB 5) "
    "for an educational tool — not legal advice. You have two tools: use `search_corpus` for questions "
    "about what a statute says or requires (passage retrieval), and `query_metadata` for factual "
    "look-ups (effective dates, cure period, enforcement authority, scope). Call a tool before "
    "answering; ground every claim in what the tools return and cite the statute section. If the tools "
    "return nothing on point, say so and suggest consulting a licensed attorney — do not guess."
)

_SEARCH_CORPUS = {
    "name": "search_corpus",
    "description": (
        "Search the statute corpus for passages relevant to a question. Optionally filter by "
        "jurisdiction ('Colorado' or 'Connecticut')."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {"type": "string", "description": "What to search for."},
            "jurisdiction": {"type": "string", "description": "Optional: Colorado or Connecticut."},
        },
        "required": ["query"],
    },
}

_QUERY_METADATA = {
    "name": "query_metadata",
    "description": (
        "Answer a factual question about the laws (effective dates, cure period, enforcement "
        "authority, scope domains) from structured metadata."
    ),
    "input_schema": {
        "type": "object",
        "properties": {"question": {"type": "string"}},
        "required": ["question"],
    },
}


def _format_chunks(chunks: list[RetrievedChunk]) -> str:
    if not chunks:
        return "(no passages found)"
    return "\n\n".join(f"[{c.citation}] {c.text}" for c in chunks)


def build_retrieval_tools(retriever, conn, llm, k: int = 8):
    """The two tools + a dispatcher wiring them to the real retrieval paths. `retriever` and `conn`
    are duck-typed (a Retriever and the metadata sqlite connection) so this module needn't import
    them and risk a cycle. Returns (tools, dispatch) for `llm.run_tools`."""

    def dispatch(name: str, args: dict) -> str:
        if name == "search_corpus":
            # Lazy import dodges the retrieval<->router import cycle (retrieval imports rules_route).
            from patchwork_assurance.core.retrieval import RetrievalFilters

            jur = args.get("jurisdiction")
            filters = RetrievalFilters(jurisdiction=jur) if jur else None
            return _format_chunks(retriever.retrieve(args["query"], filters, k))
        if name == "query_metadata":
            from patchwork_assurance.core.metadata_query import query_metadata

            rows = query_metadata(args["question"], conn, llm)
            return json.dumps(rows) if rows else "(no matching metadata)"
        return f"(unknown tool: {name})"

    return [_SEARCH_CORPUS, _QUERY_METADATA], dispatch


def agentic_route(question: str, llm, retriever, conn, k: int = 8) -> ToolRunResult:
    """Let the model choose its retrieval tool(s) and answer. COST-BEARING (see module docstring).
    The returned `tools_called` is the observed route; the text is the grounded answer."""
    tools, dispatch = build_retrieval_tools(retriever, conn, llm, k)
    return llm.run_tools(_AGENTIC_SYSTEM, [Msg(role="user", content=question)], tools, dispatch)
