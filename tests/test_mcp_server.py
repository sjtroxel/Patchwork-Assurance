"""MCP server tests — offline, StubLLM, no API key, no corpus load.

Strategy: monkeypatch `server._deps` with a minimal Deps built from the fake-law fixture
so every tool call uses deterministic, zero-spend code paths.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import patchwork_assurance.mcp.server as server
from patchwork_assurance.config import settings
from patchwork_assurance.core.contracts import Situation
from patchwork_assurance.core.corpus.metadata import LawMetadata
from patchwork_assurance.core.llm import StubLLM
from patchwork_assurance.core.metadata_query import MetadataIntent, build_metadata_db
from patchwork_assurance.core.prompts import DISCLAIMER
from patchwork_assurance.mcp.server import Deps, mcp

FIXTURE_DIR = Path(__file__).parent / "fixtures"

_EXPECTED_TOOLS = {
    "list_jurisdictions",
    "check_scope",
    "search_corpus",
    "generate_memo",
    "query_metadata",
}


class _StubRetriever:
    def retrieve(self, query, filters=None, k=5):
        return []

    def query(self, query, filters=None, k=5, mode="filtered"):
        return []


def _fake_laws() -> list[LawMetadata]:
    import yaml

    return [LawMetadata(**yaml.safe_load((FIXTURE_DIR / "fake-law.meta.yaml").read_text()))]


@pytest.fixture()
def test_deps(monkeypatch):
    """Inject a minimal Deps with StubLLM and the fake-law fixture; no corpus load."""
    # The multi_agent memo default builds its reviewer LLM from settings, which reads llm_provider
    # from .env; pin it to 'stub' or generate_memo fires live OpenRouter calls. Offline discipline.
    monkeypatch.setattr(settings, "llm_provider", "stub")
    laws = _fake_laws()
    deps = Deps(
        retriever=_StubRetriever(),
        laws=laws,
        memo_llm=StubLLM(),
        meta_conn=build_metadata_db(laws),
    )
    monkeypatch.setattr(server, "_deps", deps)
    return deps


@pytest.fixture()
def meta_test_deps(monkeypatch):
    """Deps where the LLM returns a valid MetadataIntent so query_metadata succeeds."""
    monkeypatch.setattr(settings, "llm_provider", "stub")
    laws = _fake_laws()
    deps = Deps(
        retriever=_StubRetriever(),
        laws=laws,
        memo_llm=StubLLM(structured=MetadataIntent(field="cure_period", jurisdiction="Testland")),
        meta_conn=build_metadata_db(laws),
    )
    monkeypatch.setattr(server, "_deps", deps)
    return deps


# ---- read-only: exactly the five expected tools ----


def test_read_only_tool_set():
    """The registered tool set is exactly the five read tools — no write tool."""
    names = {t.name for t in mcp._tool_manager.list_tools()}
    assert names == _EXPECTED_TOOLS


# ---- schema: Pydantic models generate valid tool input schemas ----


def test_check_scope_schema_has_situation():
    tools = {t.name: t for t in mcp._tool_manager.list_tools()}
    params = tools["check_scope"].parameters
    assert "situation" in params.get("properties", {})


def test_generate_memo_schema_has_situation():
    tools = {t.name: t for t in mcp._tool_manager.list_tools()}
    params = tools["generate_memo"].parameters
    assert "situation" in params.get("properties", {})


def test_search_corpus_schema_fields():
    tools = {t.name: t for t in mcp._tool_manager.list_tools()}
    props = tools["search_corpus"].parameters.get("properties", {})
    assert "query" in props
    assert "jurisdiction" in props
    assert "k" in props


# ---- tool-wrapper unit tests ----


def test_list_jurisdictions(test_deps):
    result = server.list_jurisdictions()
    assert "jurisdictions" in result
    assert "Testland" in result["jurisdictions"]
    assert "decision_domains" in result
    assert "roles" in result


def test_check_scope_returns_results(test_deps):
    situation = Situation(jurisdictions=["Testland"], decision_domains=["employment"])
    result = server.check_scope(situation)
    assert "results" in result
    assert isinstance(result["results"], list)
    assert len(result["results"]) == 1
    assert result["results"][0]["law_id"] == "fake-law"


def test_search_corpus_returns_chunks(test_deps):
    result = server.search_corpus("deployer notice", jurisdiction="Testland")
    assert "chunks" in result
    assert isinstance(result["chunks"], list)


def test_generate_memo_returns_memo(test_deps):
    situation = Situation(jurisdictions=["Testland"], decision_domains=["employment"])
    result = server.generate_memo(situation)
    assert "per_law" in result
    assert "disclaimer" in result


def test_query_metadata_returns_rows(meta_test_deps):
    result = server.query_metadata("What is the cure period for Testland?")
    assert "rows" in result
    assert isinstance(result["rows"], list)


# ---- disclaimer: every tool output carries the not-legal-advice framing ----


def test_disclaimer_list_jurisdictions(test_deps):
    assert server.list_jurisdictions()["disclaimer"] == DISCLAIMER


def test_disclaimer_check_scope(test_deps):
    situation = Situation()
    assert server.check_scope(situation)["disclaimer"] == DISCLAIMER


def test_disclaimer_search_corpus(test_deps):
    assert server.search_corpus("notice")["disclaimer"] == DISCLAIMER


def test_disclaimer_generate_memo(test_deps):
    situation = Situation()
    result = server.generate_memo(situation)
    assert result.get("disclaimer") == DISCLAIMER


def test_disclaimer_query_metadata(meta_test_deps):
    assert server.query_metadata("effective date?")["disclaimer"] == DISCLAIMER
