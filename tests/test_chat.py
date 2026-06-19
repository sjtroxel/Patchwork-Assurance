"""Chat RAG tests — offline, StubLLM, no API key."""

from patchwork_assurance.core.chat import chat, chat_stream
from patchwork_assurance.core.contracts import ChatTurn, Msg, RetrievedChunk
from patchwork_assurance.core.llm import StubLLM

# ---- stub helpers ----

CHUNK = RetrievedChunk(
    text="Deployers must provide notice.",
    citation="CO SB 26-189 § 6-1-1703(1)",
    section_number="6-1-1703",
    section_heading="Deployer duties",
    jurisdiction="CO",
    law_id="co-sb-26-189",
    score=0.9,
)


class _StubRetriever:
    def __init__(self, chunks):
        self._chunks = chunks

    def retrieve(self, query, filters=None, k=5):
        return self._chunks[:k]


MESSAGES = [Msg(role="user", content="What notice must deployers provide?")]


def test_chat_returns_chat_turn():
    llm = StubLLM(text="Deployers must provide notice per § 6-1-1703(1).")
    retriever = _StubRetriever([CHUNK])
    result = chat(MESSAGES, retriever, llm)
    assert isinstance(result, ChatTurn)


def test_chat_reply_is_stub_text():
    text = "Deployers must provide notice per § 6-1-1703(1)."
    llm = StubLLM(text=text)
    retriever = _StubRetriever([CHUNK])
    result = chat(MESSAGES, retriever, llm)
    assert result.reply == text


def test_chat_citations_from_chunks():
    llm = StubLLM(text="(stub)")
    retriever = _StubRetriever([CHUNK])
    result = chat(MESSAGES, retriever, llm)
    # citations are now section-level pinpoints, not the law-wide citation (#1)
    assert "CO § 6-1-1703" in result.citations


def test_chat_empty_history_uses_last_user():
    """If no user message in history, grounding query is empty string — should not crash."""
    llm = StubLLM(text="(stub)")
    retriever = _StubRetriever([CHUNK])
    result = chat([], retriever, llm)
    assert isinstance(result, ChatTurn)


def test_chat_stream_yields_tokens():
    text = "Deployers must provide notice."
    llm = StubLLM(text=text)
    retriever = _StubRetriever([CHUNK])
    _citations, token_iter = chat_stream(MESSAGES, retriever, llm)
    tokens = list(token_iter)
    assert len(tokens) > 0
    # StubLLM.stream yields words split by whitespace
    assert "".join(tokens) == "".join(text.split())


def test_chat_stream_is_iterator():
    llm = StubLLM(text="hello world")
    retriever = _StubRetriever([CHUNK])
    _citations, token_iter = chat_stream(MESSAGES, retriever, llm)
    # token_iter should be an iterator, not a list
    assert hasattr(token_iter, "__iter__") and hasattr(token_iter, "__next__")


def test_chat_stream_returns_citations():
    llm = StubLLM(text="(stub)")
    retriever = _StubRetriever([CHUNK])
    citations, _token_iter = chat_stream(MESSAGES, retriever, llm)
    assert isinstance(citations, list)
    assert "CO § 6-1-1703" in citations


def test_chat_no_chunks_still_returns():
    """Empty retriever → no grounding text → should still produce a ChatTurn."""
    llm = StubLLM(text="I could not find relevant statute text.")
    retriever = _StubRetriever([])
    result = chat(MESSAGES, retriever, llm)
    assert isinstance(result, ChatTurn)
    assert result.citations == []
