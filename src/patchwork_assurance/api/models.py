from pydantic import BaseModel

from patchwork_assurance.core.contracts import (  # noqa: F401 — re-exported for route use
    ComplianceMemo,
    CorpusVocab,
    Msg,
    Situation,
)


# /chat: the request wraps the stateless full message history.
class ChatRequest(BaseModel):
    messages: list[Msg]


# /chat terminal SSE event payload — emitted once, after all token frames.
class ChatSources(BaseModel):
    citations: list[str]  # section-level pinpoints, e.g. "Colorado § 6-1-1703"
    disclaimer: str  # the not-legal-advice line rides in the payload, not just the UI


# /health readiness — not a pinned API contract, fields may grow.
class HealthResponse(BaseModel):
    api: str
    core: dict  # {status, layer, version, corpus_size}
    embedding_model: str | None
    chat_model: str
    memo_model: str


# /memo-quota — remaining memo allowance for the caller (keyed on the UI-forwarded client IP).
class MemoQuota(BaseModel):
    limit: int  # 0 = unlimited
    used: int
    remaining: int
