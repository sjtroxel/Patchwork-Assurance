"""Live smoke tests — hit the real Anthropic API and the real corpus.

Gated behind the `live` marker (deselected by default via pyproject `addopts = "-m 'not live'"`),
so CI and a keyless `make test` never run these. Run manually with a key:

    ANTHROPIC_API_KEY=sk-... pytest -m live

These are the ONLY tests that exercise the AnthropicLLM path end-to-end (does Haiku return a
schema-valid ComplianceMemo via messages.parse; does streaming/chat round-trip). They also require
the Phase 1 Chroma store at .chroma to be populated.
"""

import os
from pathlib import Path

import pytest

from patchwork_assurance.config import Settings
from patchwork_assurance.core.chat import chat
from patchwork_assurance.core.contracts import ChatTurn, ComplianceMemo, Msg, Situation
from patchwork_assurance.core.embeddings import FastEmbedEmbedder
from patchwork_assurance.core.llm import build_llm
from patchwork_assurance.core.memo import generate_memo
from patchwork_assurance.core.retrieval import Retriever
from patchwork_assurance.core.scope import applicable_laws, load_law_metadata
from patchwork_assurance.core.vectorstore import ChromaVectorStore

pytestmark = pytest.mark.live


@pytest.fixture
def live_llm():
    if not os.environ.get("ANTHROPIC_API_KEY"):
        pytest.skip("ANTHROPIC_API_KEY not set")
    return build_llm(Settings(llm_provider="anthropic"))


@pytest.fixture
def retriever():
    if not Path(".chroma").exists():
        pytest.skip("no .chroma store (run the Phase 1 loader first)")
    emb = FastEmbedEmbedder()
    return Retriever(ChromaVectorStore(".chroma", emb.model_name), emb)


def test_live_memo(live_llm, retriever):
    laws = load_law_metadata(Path("corpus"))
    situation = Situation(
        jurisdictions=["Colorado"], decision_domains=["employment"], roles=["deployer"]
    )
    scope = applicable_laws(situation, laws)
    memo = generate_memo(situation, scope, retriever, live_llm)
    assert isinstance(memo, ComplianceMemo)
    assert memo.disclaimer  # the not-legal-advice line is always set
    assert memo.per_law  # at least one law finding


def test_live_chat(live_llm, retriever):
    turn = chat(
        [
            Msg(
                role="user",
                content="What must a deployer in Colorado do before an automated employment decision?",
            )
        ],
        retriever,
        live_llm,
    )
    assert isinstance(turn, ChatTurn)
    assert turn.reply
