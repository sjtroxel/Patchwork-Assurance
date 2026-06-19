import json
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sse_starlette.sse import EventSourceResponse
from starlette.concurrency import iterate_in_threadpool, run_in_threadpool

from patchwork_assurance.api.models import ChatRequest, ChatSources, HealthResponse
from patchwork_assurance.config import settings
from patchwork_assurance.core.chat import chat_stream
from patchwork_assurance.core.contracts import ComplianceMemo, Situation
from patchwork_assurance.core.embeddings import FastEmbedEmbedder
from patchwork_assurance.core.health import core_status
from patchwork_assurance.core.llm import LLMError, build_llm
from patchwork_assurance.core.memo import generate_memo
from patchwork_assurance.core.prompts import DISCLAIMER
from patchwork_assurance.core.retrieval import Retriever
from patchwork_assurance.core.scope import applicable_laws, load_law_metadata
from patchwork_assurance.core.vectorstore import ChromaVectorStore


@asynccontextmanager
async def lifespan(app: FastAPI):
    embedder = FastEmbedEmbedder()
    store = ChromaVectorStore(settings.chroma_path, embedder.model_name)
    app.state.retriever = Retriever(store, embedder)
    app.state.laws = load_law_metadata(Path(settings.corpus_path))
    app.state.embedding_model = embedder.model_name
    # Build the LLM client once — for AnthropicLLM this owns an httpx connection pool, so
    # rebuilding per request would churn connections. Same "load once, inject" rule as above.
    app.state.llm = build_llm(settings)
    yield


app = FastAPI(title="Patchwork Assurance API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- dependency functions ----


def get_retriever(request: Request):
    return request.app.state.retriever


def get_laws(request: Request):
    return request.app.state.laws


def get_llm(request: Request):
    # Prefer the lifespan-cached client; fall back to a fresh build when the lifespan did not
    # run (offline unit tests construct TestClient(app) without the context manager).
    llm = getattr(request.app.state, "llm", None)
    return llm if llm is not None else build_llm(settings)


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
        generation_model=settings.generation_model,
    )


@app.post("/analyze", response_model=ComplianceMemo)
def analyze(
    situation: Situation,
    retriever=Depends(get_retriever),
    laws=Depends(get_laws),
    llm=Depends(get_llm),
) -> ComplianceMemo:
    scope = applicable_laws(situation, laws)
    return generate_memo(situation, scope, retriever, llm)


@app.post("/chat")
async def chat_endpoint(
    body: ChatRequest,
    retriever=Depends(get_retriever),
    llm=Depends(get_llm),
):
    # chat_stream does the (blocking, CPU-bound) embed + retrieve up front, so run it in the
    # threadpool to keep the event loop free. Errors here are raised BEFORE the response starts,
    # so the exception handlers map them (LLMError → 502, ValueError → 500).
    citations, token_iter = await run_in_threadpool(chat_stream, body.messages, retriever, llm)

    async def events():
        # Once streaming starts the status is already 200, so a mid-stream failure can't be an
        # HTTP error code — surface it as a terminal SSE 'error' event so the client knows the
        # answer is incomplete (instead of the stream just going silent).
        try:
            async for token in iterate_in_threadpool(token_iter):
                yield {"event": "token", "data": token}
        except LLMError as exc:
            yield {"event": "error", "data": json.dumps({"detail": f"Upstream LLM error: {exc}"})}
            return
        sources = ChatSources(citations=citations, disclaimer=DISCLAIMER)
        yield {"event": "sources", "data": sources.model_dump_json()}

    return EventSourceResponse(events())
