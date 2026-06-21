from collections.abc import Iterator

from patchwork_assurance.core.contracts import ChatTurn, Msg
from patchwork_assurance.core.corpus.metadata import LawMetadata
from patchwork_assurance.core.prompts import CHAT_SYSTEM, render_grounding, render_law_facts


def _system(laws: list[LawMetadata] | None, grounding: str) -> str:
    """Persona + the authoritative law-facts card (guardrail) + the retrieved excerpts."""
    facts = render_law_facts(laws or [])
    parts = [CHAT_SYSTEM]
    if facts:
        parts.append(facts)
    parts.append(grounding)
    return "\n\n".join(parts)


def _ground(messages: list[Msg], retriever) -> tuple[str, list[str]]:
    last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
    # k is generous so the relevant sections surface even when the question phrasing matches an
    # adjacent provision more strongly; the law-facts card backstops any retrieval gap.
    chunks = retriever.retrieve(last_user, k=8)
    # Section-level pinpoints, deduped but order-preserving — the law-wide citation repeats per
    # chunk and is useless as a per-claim cite (#1).
    seen: set[str] = set()
    citations: list[str] = []
    for c in chunks:
        if c.pinpoint not in seen:
            seen.add(c.pinpoint)
            citations.append(c.pinpoint)
    return render_grounding(chunks), citations


def chat(messages: list[Msg], retriever, llm, laws: list[LawMetadata] | None = None) -> ChatTurn:
    grounding, citations = _ground(messages, retriever)
    reply = llm.complete(_system(laws, grounding), messages)
    return ChatTurn(reply=reply, citations=citations)


def chat_stream(
    messages: list[Msg], retriever, llm, laws: list[LawMetadata] | None = None
) -> tuple[list[str], Iterator[str]]:
    """Returns (citations, token_iterator). Citations are resolved from grounding before streaming
    so the SSE endpoint can emit a terminal sources event without retrieving twice."""
    grounding, citations = _ground(messages, retriever)
    return citations, llm.stream(_system(laws, grounding), messages)
