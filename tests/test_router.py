"""Router + tool-use tests (Phase 8 batch 4) — offline, zero tokens.

Proves the WIRING: the rules router's deterministic cue mapping, the StubLLM tool-use loop driving a
real dispatcher, the agentic router returning the chosen tool names, and query(mode="routed")
dispatching to the routed chunk mode. Whether a real model routes *well* is a live/paid check
(deferred, mirrors the Phase 6 judged run)."""

from pathlib import Path

import yaml

from patchwork_assurance.core.contracts import Msg, RetrievedChunk
from patchwork_assurance.core.corpus.metadata import LawMetadata
from patchwork_assurance.core.llm import StubLLM
from patchwork_assurance.core.metadata_query import build_metadata_db
from patchwork_assurance.core.retrieval import RetrievalFilters, Retriever
from patchwork_assurance.core.router import agentic_route, build_retrieval_tools, rules_route

FIXTURES = Path(__file__).parent / "fixtures"


# --- minimal offline stubs (repo convention: each test file is self-contained) ---------------------


class _StubEmbedder:
    model_name = "test-model"

    def embed(self, texts):
        return [[0.1] * 4 for _ in texts]


class _StubStore:
    def __init__(self, chunks):
        self._chunks = chunks

    def embedding_model(self):
        return "test-model"

    def query(self, embedding, k, where=None):
        chosen = self._chunks[:k]
        return {
            "documents": [[c["text"] for c in chosen]],
            "metadatas": [
                [
                    {
                        "citation": c["citation"],
                        "section_number": c["section_number"],
                        "section_heading": c["section_heading"],
                        "jurisdiction": c["jurisdiction"],
                        "law_id": c["law_id"],
                        "chunk_index": c.get("chunk_index", 0),
                    }
                    for c in chosen
                ]
            ],
            "distances": [[0.1] * len(chosen)],
        }


SAMPLE_CHUNKS = [
    {
        "text": "Deployers must provide notice.",
        "citation": "CO SB 26-189 § 6-1-1703(1)",
        "section_number": "6-1-1703",
        "section_heading": "Deployer duties",
        "jurisdiction": "CO",
        "law_id": "co-sb-26-189",
    },
]


def _conn():
    base = yaml.safe_load((FIXTURES / "fake-law.meta.yaml").read_text())
    return build_metadata_db([LawMetadata(**base)])


# --- rules router (deterministic) ------------------------------------------------------------------


def test_rules_route_citation_goes_hybrid():
    assert rules_route("What does section 6-1-1704 require?").mode == "hybrid"


def test_rules_route_defined_term_goes_hybrid():
    assert rules_route("How is 'substantial factor' defined?").mode == "hybrid"


def test_rules_route_factual_goes_hybrid():
    assert rules_route("When does the Colorado law take effect?").mode == "hybrid"


def test_rules_route_conceptual_goes_filtered():
    assert rules_route("Does my hiring tool need consumer notices?").mode == "filtered"


# --- tool-use loop via StubLLM (drives the real dispatcher) ----------------------------------------


def test_stub_run_tools_calls_dispatch_and_returns_names():
    calls = []

    def dispatch(name, args):
        calls.append((name, args))
        return "ok"

    llm = StubLLM(text="final answer", tool_script=[("search_corpus", {"query": "notice"})])
    result = llm.run_tools("sys", [Msg(role="user", content="q")], [], dispatch)
    assert result.text == "final answer"
    assert result.tools_called == ["search_corpus"]
    assert calls == [("search_corpus", {"query": "notice"})]


def test_stub_run_tools_empty_script_answers_directly():
    llm = StubLLM(text="no tools needed")
    result = llm.run_tools("sys", [Msg(role="user", content="q")], [], lambda n, a: "")
    assert result.text == "no tools needed" and result.tools_called == []


# --- agentic router wiring -------------------------------------------------------------------------


def test_agentic_route_search_corpus_wires_to_retriever():
    retriever = Retriever(_StubStore(SAMPLE_CHUNKS), _StubEmbedder())
    llm = StubLLM(text="grounded answer", tool_script=[("search_corpus", {"query": "notice"})])
    result = agentic_route("What notice is required?", llm, retriever, _conn())
    assert result.tools_called == ["search_corpus"]
    assert result.text == "grounded answer"


def test_agentic_route_query_metadata_wires_to_structured_path():
    retriever = Retriever(_StubStore(SAMPLE_CHUNKS), _StubEmbedder())
    # The structured path itself needs an LLM for intent extraction; the stub supplies a fixed intent.
    from patchwork_assurance.core.metadata_query import MetadataIntent

    llm = StubLLM(
        text="effective 2027",
        structured=MetadataIntent(field="signed_date"),
        tool_script=[("query_metadata", {"question": "when effective?"})],
    )
    result = agentic_route("When is it effective?", llm, retriever, _conn())
    assert result.tools_called == ["query_metadata"]


def test_build_retrieval_tools_exposes_both_tools():
    tools, _ = build_retrieval_tools(object(), object(), StubLLM())
    assert {t["name"] for t in tools} == {"search_corpus", "query_metadata"}


# --- query(mode="routed") dispatch -----------------------------------------------------------------


def test_query_routed_citation_uses_hybrid_path(monkeypatch):
    # Routed citation question → rules_route picks hybrid → fusion runs (lexical present).
    from patchwork_assurance.core.lexical import LexicalIndex

    chunks = [
        RetrievedChunk(
            text="Notice under 6-1-1704.",
            citation="CO 6-1-1704",
            section_number="6-1-1704",
            section_heading="Notice",
            jurisdiction="CO",
            law_id="co-sb-26-189",
            score=0.9,
            chunk_index=0,
        )
    ]
    lex = LexicalIndex(chunks)
    retriever = Retriever(_StubStore(SAMPLE_CHUNKS), _StubEmbedder(), lex)
    out = retriever.query("What does 6-1-1704 require?", RetrievalFilters(), k=3, mode="routed")
    assert out  # routed → hybrid produced a fused ranking without error


def test_query_routed_conceptual_matches_filtered():
    retriever = Retriever(_StubStore(SAMPLE_CHUNKS), _StubEmbedder())
    routed = retriever.query("Does my tool need notices?", None, k=2, mode="routed")
    filtered = retriever.query("Does my tool need notices?", None, k=2, mode="filtered")
    assert [c.citation for c in routed] == [c.citation for c in filtered]
