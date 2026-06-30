"""Phase 10 — MCP server.  Thin wrapper: imports core/, exposes read-only tools, re-implements
no business logic.  Deps are built lazily on first tool call so imports are cheap and tests can
inject their own Deps without triggering a full corpus load."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from patchwork_assurance.config import settings
from patchwork_assurance.core.contracts import Situation
from patchwork_assurance.core.corpus.loader import load_corpus
from patchwork_assurance.core.embeddings import FastEmbedEmbedder
from patchwork_assurance.core.lexical import build_lexical_index
from patchwork_assurance.core.llm import build_llm
from patchwork_assurance.core.memo import generate_memo as core_generate_memo
from patchwork_assurance.core.meta import corpus_vocab
from patchwork_assurance.core.metadata_query import build_metadata_db
from patchwork_assurance.core.metadata_query import query_metadata as core_query_metadata
from patchwork_assurance.core.prompts import DISCLAIMER
from patchwork_assurance.core.retrieval import RetrievalFilters, Retriever
from patchwork_assurance.core.scope import applicable_laws, load_law_metadata
from patchwork_assurance.core.vectorstore import ChromaVectorStore


@dataclass
class Deps:
    retriever: Retriever
    laws: list
    memo_llm: object
    meta_conn: sqlite3.Connection


def build_deps() -> Deps:
    embedder = FastEmbedEmbedder()
    store = ChromaVectorStore(settings.chroma_path, embedder.model_name)
    if store.count() == 0:
        load_corpus(Path(settings.corpus_path), store, embedder)
    lexical = build_lexical_index(Path(settings.corpus_path)) if settings.enable_lexical else None
    laws = load_law_metadata(Path(settings.corpus_path))
    return Deps(
        retriever=Retriever(store, embedder, lexical),
        laws=laws,
        memo_llm=build_llm(settings, settings.memo_model),
        meta_conn=build_metadata_db(laws),
    )


_deps: Deps | None = None


def _get_deps() -> Deps:
    global _deps
    if _deps is None:
        _deps = build_deps()
    return _deps


mcp = FastMCP("Patchwork Assurance")


@mcp.tool()
def list_jurisdictions() -> dict:
    """List the jurisdictions, decision domains, and roles the corpus covers (free, deterministic)."""
    vocab = corpus_vocab(_get_deps().laws)
    return {**vocab.model_dump(), "disclaimer": DISCLAIMER}


@mcp.tool()
def check_scope(situation: Situation) -> dict:
    """Deterministic scope screen: which corpus laws apply to this situation (free, no LLM)."""
    results = applicable_laws(situation, _get_deps().laws)
    return {"results": [r.model_dump() for r in results], "disclaimer": DISCLAIMER}


@mcp.tool()
def search_corpus(
    query: str,
    jurisdiction: str | None = None,
    scope_domain: str | None = None,
    law_id: str | None = None,
    k: int = 8,
) -> dict:
    """Grounded passage lookup over the statute corpus, with citations (free; local embeddings)."""
    filters = RetrievalFilters(jurisdiction=jurisdiction, scope_domain=scope_domain, law_id=law_id)
    chunks = _get_deps().retriever.query(query, filters, k=k, mode=settings.retrieval_mode)
    return {"chunks": [c.model_dump() for c in chunks], "disclaimer": DISCLAIMER}


@mcp.tool()
def generate_memo(situation: Situation) -> dict:
    """Full educational compliance memo (COST-BEARING — Sonnet). Needs LLM_PROVIDER=anthropic + a key."""
    deps = _get_deps()
    scope = applicable_laws(situation, deps.laws)
    memo = core_generate_memo(situation, scope, deps.retriever, deps.memo_llm, deps.laws)
    return memo.model_dump()


@mcp.tool()
def query_metadata(question: str) -> dict:
    """Factual metadata questions (effective dates, cure periods, scope) over the law-metadata table
    (COST-BEARING — one LLM call; fails closed to an empty list)."""
    deps = _get_deps()
    rows = core_query_metadata(question, deps.meta_conn, deps.memo_llm, mode="intent")
    return {"rows": rows, "disclaimer": DISCLAIMER}


if __name__ == "__main__":
    _get_deps()  # warm up before accepting connections
    mcp.run(transport="stdio")
