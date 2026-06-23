import json
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse
from starlette.concurrency import iterate_in_threadpool, run_in_threadpool

from patchwork_assurance.api.models import ChatRequest, ChatSources, HealthResponse, MemoQuota
from patchwork_assurance.config import settings
from patchwork_assurance.core import grounding, obs
from patchwork_assurance.core.chat import chat_stream
from patchwork_assurance.core.contracts import ComplianceMemo, CorpusVocab, Situation
from patchwork_assurance.core.corpus.loader import load_corpus
from patchwork_assurance.core.embeddings import FastEmbedEmbedder
from patchwork_assurance.core.health import core_status
from patchwork_assurance.core.llm import LLMError, build_llm
from patchwork_assurance.core.memo import generate_memo
from patchwork_assurance.core.meta import corpus_vocab
from patchwork_assurance.core.prompts import DISCLAIMER
from patchwork_assurance.core.retrieval import Retriever
from patchwork_assurance.core.scope import applicable_laws, load_law_metadata
from patchwork_assurance.core.vectorstore import ChromaVectorStore


@asynccontextmanager
async def lifespan(app: FastAPI):
    embedder = FastEmbedEmbedder()
    store = ChromaVectorStore(settings.chroma_path, embedder.model_name)
    # The Chroma index is git-ignored, so a fresh deploy boots with an empty collection. Build it
    # from the committed corpus on first boot; idempotent (deterministic chunk IDs, skip when present)
    # so an existing local index is left untouched. A 2-statute corpus indexes in seconds.
    if store.count() == 0:
        n = load_corpus(Path(settings.corpus_path), store, embedder)
        print(f"[startup] built corpus index: {n} chunks ({store.count()} total).")
    app.state.retriever = Retriever(store, embedder)
    app.state.laws = load_law_metadata(Path(settings.corpus_path))
    app.state.embedding_model = embedder.model_name
    # Real corpus section index, for the runtime grounding guard (Phase 7): jurisdiction -> sections.
    app.state.corpus_sections = {
        jurisdiction: set(texts)
        for jurisdiction, texts in grounding.corpus_section_texts(
            Path(settings.corpus_path)
        ).items()
    }
    # Build the LLM clients once — for AnthropicLLM each owns an httpx connection pool, so
    # rebuilding per request would churn connections. Two-model split: chat=Haiku, memo=Sonnet.
    app.state.chat_llm = build_llm(settings, settings.chat_model)
    app.state.memo_llm = build_llm(settings, settings.memo_model)
    yield


app = FastAPI(title="Patchwork Assurance API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Assign/propagate a request id for log correlation. Reads an inbound X-Request-ID (so the UI can
    correlate its hop) or generates one; sets the contextvar the Seam-4 logger reads; echoes it back."""
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex
    token = obs.set_request_id(rid)
    try:
        response = await call_next(request)
    finally:
        obs.reset_request_id(token)
    response.headers["X-Request-ID"] = rid
    return response


# ---- dependency functions ----


def get_retriever(request: Request):
    return request.app.state.retriever


def get_laws(request: Request):
    return request.app.state.laws


def get_sections(request: Request):
    # The real corpus section index for the grounding guard. Empty when the lifespan hasn't run
    # (offline unit tests) — the guard then no-ops rather than false-flag.
    return getattr(request.app.state, "corpus_sections", {})


def get_chat_llm(request: Request):
    # Prefer the lifespan-cached client; fall back to a fresh build when the lifespan did not run
    # (offline unit tests construct TestClient(app) without the context manager).
    llm = getattr(request.app.state, "chat_llm", None)
    return llm if llm is not None else build_llm(settings, settings.chat_model)


def get_memo_llm(request: Request):
    llm = getattr(request.app.state, "memo_llm", None)
    return llm if llm is not None else build_llm(settings, settings.memo_model)


# ---- memo rate limit (Sonnet cost cap) ----
# In-memory per-IP daily counter: stores counts (not user inputs), resets on restart — consistent
# with the statelessness invariant. Per-process, so the backend stays single-instance for v1 (a
# shared/hosting-layer limit would be needed if it ever scales). Chat is intentionally unlimited.
_memo_counts: dict[str, tuple[str, int]] = {}


def _client_ip(request: Request) -> str:
    # The UI proxies to the API, so the socket peer is the UI server, not the end user. The UI
    # forwards the real browser IP (from st.context.ip_address) as X-Client-IP so the limit is
    # per-user. Fall back to X-Forwarded-For, then the socket peer. All spoofable: best-effort cost
    # control, not a security control.
    forwarded = request.headers.get("x-client-ip")
    if forwarded:
        return forwarded.strip()
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def _memo_used_today(ip: str) -> int:
    today = datetime.now(UTC).date().isoformat()
    day, count = _memo_counts.get(ip, (today, 0))
    return count if day == today else 0


def memo_rate_limit(request: Request) -> None:
    limit = settings.memo_daily_limit_per_ip
    if limit <= 0:  # 0 disables the limit
        return
    ip = _client_ip(request)
    used = _memo_used_today(ip)
    if used >= limit:
        raise HTTPException(
            status_code=429,
            detail=(
                f"You've reached today's limit of {limit} compliance memos. Chat is unlimited, or "
                "try again tomorrow."
            ),
        )
    _memo_counts[ip] = (datetime.now(UTC).date().isoformat(), used + 1)


# ---- exception handlers ----


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    # Safety net for per-request ValueErrors. The main one it was written for — the embedding
    # model mismatch (rag.md rule 1) — actually raises in Retriever.__init__ during lifespan, so
    # it fails startup, not a request. This stays as defense for any other in-request ValueError.
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.exception_handler(LLMError)
async def llm_error_handler(request: Request, exc: LLMError):
    # core wraps any provider failure into LLMError, so the transport layer never imports a
    # vendor SDK. (Fires for /analyze; a mid-stream /chat failure ends the stream instead.)
    return JSONResponse(status_code=502, content={"detail": f"Upstream LLM error: {exc}"})


# ---- routes ----


@app.get("/health", response_model=HealthResponse)
def health(request: Request) -> HealthResponse:
    return HealthResponse(
        api="ok",
        core=core_status(),
        embedding_model=getattr(request.app.state, "embedding_model", None),
        chat_model=settings.chat_model,
        memo_model=settings.memo_model,
    )


@app.get("/meta", response_model=CorpusVocab)
def meta(laws=Depends(get_laws)) -> CorpusVocab:
    # Corpus-derived form vocabulary so the UI populates itself; a new jurisdiction needs no UI change.
    return corpus_vocab(laws)


@app.get("/memo-quota", response_model=MemoQuota)
def memo_quota(request: Request) -> MemoQuota:
    # Read-only: the caller's remaining memo allowance for the day. Does NOT consume a memo.
    limit = settings.memo_daily_limit_per_ip
    used = _memo_used_today(_client_ip(request))
    return MemoQuota(limit=limit, used=used, remaining=max(0, limit - used) if limit > 0 else 0)


@app.post("/analyze", response_model=ComplianceMemo)
def analyze(
    situation: Situation,
    retriever=Depends(get_retriever),
    laws=Depends(get_laws),
    llm=Depends(get_memo_llm),
    sections=Depends(get_sections),
    _rl: None = Depends(memo_rate_limit),
) -> ComplianceMemo:
    scope = applicable_laws(situation, laws)
    memo = generate_memo(situation, scope, retriever, llm, laws)
    # Grounding guard: every section the memo cites must be a real corpus section. A hijacked memo
    # often cites a fabricated one. Log + flag (not block) — citation identifiers, not user content.
    if sections:
        cited = [ob.citation for finding in memo.per_law for ob in finding.obligations]
        unresolved = grounding.unresolved_citations(cited, sections)
        if unresolved:
            obs.log_event(
                "grounding_guard", surface="memo", unresolved=len(unresolved), citations=unresolved
            )
    return memo


@app.post("/chat")
async def chat_endpoint(
    body: ChatRequest,
    retriever=Depends(get_retriever),
    llm=Depends(get_chat_llm),
    laws=Depends(get_laws),
    sections=Depends(get_sections),
):
    # chat_stream does the (blocking, CPU-bound) embed + retrieve up front, so run it in the
    # threadpool to keep the event loop free. Errors here are raised BEFORE the response starts,
    # so the exception handlers map them (LLMError → 502, ValueError → 500). `laws` feeds the
    # authoritative law-facts guardrail.
    citations, token_iter = await run_in_threadpool(
        chat_stream, body.messages, retriever, llm, laws
    )

    async def events():
        # Once streaming starts the status is already 200, so a mid-stream failure can't be an
        # HTTP error code — surface it as a terminal SSE 'error' event so the client knows the
        # answer is incomplete (instead of the stream just going silent).
        buffer: list[str] = []
        try:
            async for token in iterate_in_threadpool(token_iter):
                buffer.append(token)
                yield {"event": "token", "data": token}
        except LLMError as exc:
            yield {"event": "error", "data": json.dumps({"detail": f"Upstream LLM error: {exc}"})}
            return
        # Grounding guard (post-stream, log-only — the reply is already sent, so chat can't block).
        # Parse section citations from the reply PROSE (the citations list is retrieval-derived and
        # always real, so it can't reveal a hijack); flag any that don't resolve to a real section.
        if sections:
            unresolved = grounding.unresolved_citations(
                grounding.cited_sections("".join(buffer)), sections
            )
            if unresolved:
                obs.log_event(
                    "grounding_guard",
                    surface="chat",
                    unresolved=len(unresolved),
                    citations=unresolved,
                )
        sources = ChatSources(citations=citations, disclaimer=DISCLAIMER)
        yield {"event": "sources", "data": sources.model_dump_json()}

    return EventSourceResponse(events())
