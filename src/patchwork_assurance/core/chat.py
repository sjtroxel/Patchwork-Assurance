from collections.abc import Iterator

from patchwork_assurance.core.contracts import ChatTurn, Msg
from patchwork_assurance.core.prompts import CHAT_SYSTEM, render_grounding


def _ground(messages: list[Msg], retriever) -> tuple[str, list[str]]:
    last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
    chunks = retriever.retrieve(last_user, k=5)
    # Section-level pinpoints, deduped but order-preserving — the law-wide citation repeats per
    # chunk and is useless as a per-claim cite (#1).
    seen: set[str] = set()
    citations: list[str] = []
    for c in chunks:
        if c.pinpoint not in seen:
            seen.add(c.pinpoint)
            citations.append(c.pinpoint)
    return render_grounding(chunks), citations


def chat(messages: list[Msg], retriever, llm) -> ChatTurn:
    grounding, citations = _ground(messages, retriever)
    reply = llm.complete(CHAT_SYSTEM + "\n\n" + grounding, messages)
    return ChatTurn(reply=reply, citations=citations)


def chat_stream(messages: list[Msg], retriever, llm) -> Iterator[str]:
    grounding, _ = _ground(messages, retriever)
    yield from llm.stream(CHAT_SYSTEM + "\n\n" + grounding, messages)
