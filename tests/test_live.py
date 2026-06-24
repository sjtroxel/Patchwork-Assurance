"""Live smoke tests — hit the real Anthropic API and the real corpus.

Gated behind the `live` marker (deselected by default via pyproject `addopts = "-m 'not live'"`),
so CI and a keyless `make test` never run these. Run manually with a key:

    ANTHROPIC_API_KEY=sk-... pytest -m live

These are the ONLY tests that exercise the AnthropicLLM path end-to-end (does Haiku return a
schema-valid ComplianceMemo via messages.parse; does streaming/chat round-trip). They also require
the Phase 1 Chroma store at .chroma to be populated.

OpenRouter (Phase 8 interlude) has its own live smoke tests below — they verify a real free model
through the OpenRouterLLM path for $0. Run them with your key + a current free model id:

    OPENROUTER_API_KEY=sk-or-... OPENROUTER_TEST_MODEL=<a :free id from openrouter.ai/models> pytest -m live

(The model id is required, not hardcoded, because the free-model lineup churns and which ones support
JSON-object / structured output varies — the structured test tells you whether the one you picked does.)
"""

import os
from pathlib import Path

import pytest
from pydantic import BaseModel

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
    s = Settings(llm_provider="anthropic")
    return build_llm(s, s.memo_model)


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


# ---- OpenRouter (free-model) live smoke tests (Phase 8 interlude) ----


class _MiniLive(BaseModel):
    name: str
    n: int


@pytest.fixture
def openrouter_llm():
    if not os.environ.get("OPENROUTER_API_KEY"):
        pytest.skip("OPENROUTER_API_KEY not set")
    model = os.environ.get("OPENROUTER_TEST_MODEL")
    if not model:
        pytest.skip("set OPENROUTER_TEST_MODEL to a current model id from openrouter.ai/models")
    return build_llm(Settings(llm_provider="openrouter"), model)


def test_live_openrouter_complete(openrouter_llm):
    out = openrouter_llm.complete(
        "You are concise.", [Msg(role="user", content="Reply with the single word: ready")]
    )
    assert out.strip()  # the free model returned some text through the OpenRouterLLM path


def test_live_openrouter_structured(openrouter_llm):
    # Whether a given free model honors JSON-object mode varies — this is the check that tells you.
    out = openrouter_llm.complete_structured(
        "Extract the fields from the message.",
        [Msg(role="user", content="name is Ada, n is 4")],
        _MiniLive,
    )
    assert out.name and isinstance(out.n, int)
