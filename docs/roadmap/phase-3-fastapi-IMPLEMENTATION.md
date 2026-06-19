# Phase 3 — IMPLEMENTATION (as-built runbook)

*The executable steps for Phase 3, prepared 2026-06-18 (Phases 0–2 complete: corpus indexed at 50
chunks; `core/` exposes retrieval, the deterministic scope screen + `ScopePolicy` dial, memo generation,
and chat RAG, all green offline behind the Seam-4 `StubLLM`). Companion to the design in
[`phase-3-fastapi.md`](phase-3-fastapi.md); the wire contracts land in [`../SPEC_V1.md`](../SPEC_V1.md)
§8. This is the builder's first FastAPI + async + SSE work — written to teach, and to reconcile the
Phase 3 plan (written before Phase 2 was built) with how Phase 2 actually turned out.*

> **High-confidence vs verify-at-build.** The route wiring, Pydantic reuse, lifespan/DI, and the
> `TestClient` tests are stable FastAPI — copy them. Two things to **verify at build**: the
> **`sse-starlette` `EventSourceResponse` API** (pinned below, but re-confirm the generator/event shape
> against the installed version) and the **Anthropic streaming** (already owned by `core.llm.stream`,
> verified in Phase 2 — Phase 3 does not re-touch the SDK).
>
> **This is a transport layer. No business logic lives here.** If a rule about scope, grounding, or
> citations shows up in a route, it is in the wrong file — it belongs in `core/` (Phase 2). The two
> `core/` touch-ups below (§1) are deliberate and reviewed; they are *grounding* logic, not transport.

---

## 0. Verified-at-build facts (2026-06-18)

- **Installed, already present (Phase 0):** `fastapi` **0.137.1**, `uvicorn` **0.49.0**, `httpx`
  **0.28.1** (the `TestClient` transport). `starlette.concurrency.iterate_in_threadpool` is present
  (ships with FastAPI — the sync→async bridge, no new dep).
- **New dependency this phase:** **`sse-starlette`** — latest available **3.4.4**. Pin it in
  `pyproject.toml` and re-freeze. Provides `EventSourceResponse` + `ServerSentEvent`.
- **`EventSourceResponse` shape (verify at build):** construct it with an **async generator** that
  yields either dicts (`{"event": "...", "data": "..."}`) or `ServerSentEvent(...)` objects. A bare
  `data` (no `event`) is the default `message` event. It handles SSE framing, keep-alive pings, and
  client-disconnect cancellation for us. Confirm the exact kwarg names (`ping`, `sep`) against 3.4.4
  before relying on them.
- **The Anthropic path is untouched here.** `core.llm.AnthropicLLM.stream` already yields a sync
  `Iterator[str]` (verified against `anthropic` 0.111.0 in Phase 2). Phase 3 only *adapts* that iterator
  to async; it does not call the SDK.

---

## 1. As-built reconciliation — where the Phase 3 plan meets the real Phase 2

The Phase 3 design doc was written **before** Phase 2 was built, so two of its signatures are stale.
Build against these corrected facts, not the plan's `§4`/`§6` pseudocode.

**1a. `/analyze` is a two-call sequence, not one.** The plan wrote `core.generate_memo(situation, llm,
retriever)`. The real Phase 2 API is:

```python
scope = applicable_laws(situation, laws)                 # deterministic screen (laws = LawMetadata list)
memo  = generate_memo(situation, scope, retriever, llm)  # actual signature: (situation, scope, retriever, llm)
```

So the route must (1) run the deterministic scope screen, then (2) generate the memo from that scope.
**Consequence for lifespan (§4):** startup must load **both** the retriever **and** the parsed
`list[LawMetadata]` (via `core.load_law_metadata(Path(settings.corpus_path))`), and hold both in
`app.state`. The scope screen uses the **default `CAUTIOUS` policy** — do not expose the policy dial on
the API surface in v1 (it's an internal strictness knob, not a client input; revisit if ever needed).

**1b. `chat_stream` currently discards the citations the SSE `sources` event needs.** Phase 2's
`chat_stream(messages, retriever, llm)` yields only token strings — internally it computes grounding +
citations but throws the citations away (`grounding, _ = _ground(...)`). The SSE terminal `sources`
event needs those citations, and re-deriving them would retrieve twice. **Fix in `core/chat.py`** (this
is grounding logic, so it belongs in core, not the route): have the streaming path surface citations
up front alongside the token iterator. Recommended minimal change:

```python
# core/chat.py — replace chat_stream with a version that hands back the (already-computed) citations.
def chat_stream(messages: list[Msg], retriever, llm) -> tuple[list[str], Iterator[str]]:
    """Returns (citations, token_iterator). Citations are known from grounding *before* streaming, so
    the SSE endpoint can stream tokens then emit a terminal 'sources' event without retrieving twice."""
    grounding, citations = _ground(messages, retriever)
    return citations, llm.stream(CHAT_SYSTEM + "\n\n" + grounding, messages)
```

Update the Phase 2 `test_chat.py` streaming tests accordingly (they currently unpack a bare iterator).
Record this as an as-built deviation in the Phase 2 doc's notes too. `chat()` (the non-streaming
full-response helper) is unchanged and still returns a `ChatTurn`.

> Both touch-ups keep the architecture honest: the route never computes scope or citations itself; it
> calls `core/` and serializes. The keystone rule holds — `core/` imports nothing from `api/`.

---

## 2. Step 1 — dependency & config

Add to `pyproject.toml` `dependencies`:

```toml
    "sse-starlette",
```

Then `pip install -e ".[dev]" && pip freeze > requirements-lock.txt`, and **pin** `sse-starlette==3.4.4`
in the as-built notes (§13) once installed.

Add to `config.py` `Settings` (everything else already exists from Phases 0–2):

```python
    cors_allow_origins: list[str] = ["http://localhost:8501"]  # the local Streamlit origin (Phase 4)
```

> `pydantic-settings` parses a JSON list from the `CORS_ALLOW_ORIGINS` env var, or a single string.
> Default is the local Streamlit port so `make dev` works with zero env; Phase 5 overrides it with the
> deployed UI origin.

---

## 3. Step 2 — request/response models (`api/models.py`)

FastAPI is Pydantic-native, so the SPEC §8 core shapes are the wire contract directly — **import and
reuse them, don't redefine** (the API contract and the core contract must not drift).

```python
from pydantic import BaseModel

from patchwork_assurance.core.contracts import ComplianceMemo, Msg, Situation  # reused as-is

# /analyze: request is core.Situation directly; response is core.ComplianceMemo directly.

# /chat: the request wraps the stateless full history.
class ChatRequest(BaseModel):
    messages: list[Msg]

# /chat terminal SSE event payload (the grounding, sent after the prose).
class ChatSources(BaseModel):
    citations: list[str]   # section-level pinpoints, e.g. "Colorado § 6-1-1703"
    disclaimer: str        # the not-legal-advice line — rides in the payload, not just the UI

# /health readiness (not a pinned contract, but typed for the pattern).
class HealthResponse(BaseModel):
    api: str
    core: dict             # {status, layer, version, corpus_size}
    embedding_model: str | None
    generation_model: str
```

`Situation` and `ComplianceMemo` are used directly as the `/analyze` request body and `response_model`.
Pin `ChatRequest` / `ChatSources` shapes in SPEC §8 (§11 of the plan; the design doc left the sources
payload open — this settles it).

---

## 4. Step 3 — app wiring: lifespan + dependency injection (`api/main.py`)

The structural FastAPI lesson. Load expensive objects **once**, inject everywhere.

```python
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI

from patchwork_assurance.config import settings
from patchwork_assurance.core.embeddings import FastEmbedEmbedder
from patchwork_assurance.core.llm import StubLLM, build_llm
from patchwork_assurance.core.retrieval import Retriever
from patchwork_assurance.core.scope import load_law_metadata
from patchwork_assurance.core.vectorstore import ChromaVectorStore


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Load the embedder + Chroma collection + law metadata ONCE. The retriever's constructor runs the
    # embedding-model mismatch guard at this point (rag.md rule 1) — a misindexed store fails startup
    # loudly, not silently per request.
    embedder = FastEmbedEmbedder()
    store = ChromaVectorStore(settings.chroma_path, embedder.model_name)
    app.state.retriever = Retriever(store, embedder)
    app.state.laws = load_law_metadata(Path(settings.corpus_path))
    app.state.embedding_model = embedder.model_name
    yield
    # nothing to tear down (stateless, no connections held)


app = FastAPI(title="Patchwork Assurance API", lifespan=lifespan)


def get_retriever(): ...     # returns app.state.retriever  (via Request)
def get_laws(): ...          # returns app.state.laws
def get_llm():               # the Seam-4 factory: "anthropic" | "stub" from config
    return build_llm(settings)
```

- **Why DI matters for tests (§9):** `app.dependency_overrides[get_llm] = lambda: StubLLM(structured=...)`
  makes the whole API run offline and deterministic in CI. This is the Phase 2 Seam 4 interface meeting
  FastAPI's DI — the payoff of building the stub.
- Dependencies pull from `app.state` via the `Request` object (`def get_retriever(request): return
  request.app.state.retriever`), so `TestClient` and the live app share one load path.

---

## 5. Step 4 — `GET /health` (real readiness)

Upgrade the Phase 0 stub to report the model wiring, so a Phase 5 deploy smoke-test can confirm the
index and models are live:

```python
@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        api="ok",
        core=core_status(),                       # {status, layer, version, corpus_size}
        embedding_model=app.state.embedding_model,
        generation_model=settings.generation_model,
    )
```

> Keep `core_status()` (Phase 1) as the corpus-size source. `/health` stays a readiness check, **not** a
> pinned contract — fields can grow.

---

## 6. Step 5 — `POST /analyze` (sync `def`, the demoable surface)

A **sync `def`** endpoint: FastAPI runs sync routes in a threadpool, so the CPU-bound embedding/retrieval
and the blocking LLM call don't stall the event loop. `core/` is sync; making this `async` would mean
blocking the loop or pointless churn.

```python
@app.post("/analyze", response_model=ComplianceMemo)
def analyze(
    situation: Situation,
    retriever=Depends(get_retriever),
    laws=Depends(get_laws),
    llm=Depends(get_llm),
) -> ComplianceMemo:
    scope = applicable_laws(situation, laws)                 # deterministic — CAUTIOUS default
    return generate_memo(situation, scope, retriever, llm)   # (situation, scope, retriever, llm)
```

- Bad input → **422** automatically (Pydantic validates `Situation`). Never a 500 for client error.
- `ComplianceMemo.disclaimer` rides in the response body — a raw API consumer still gets the
  not-legal-advice line.

---

## 7. Step 6 — `POST /chat` (async SSE, the async rep)

The honest tension: **`core/` is sync, SSE wants async.** Bridge with `iterate_in_threadpool` so the
blocking token pulls happen off the event loop, and let `sse-starlette` own the framing.

```python
from sse_starlette.sse import EventSourceResponse
from starlette.concurrency import iterate_in_threadpool

from patchwork_assurance.core.chat import chat_stream      # now returns (citations, token_iter)
from patchwork_assurance.core.prompts import DISCLAIMER


@app.post("/chat")
async def chat_endpoint(
    body: ChatRequest,
    retriever=Depends(get_retriever),
    llm=Depends(get_llm),
):
    citations, token_iter = chat_stream(body.messages, retriever, llm)

    async def events():
        async for token in iterate_in_threadpool(token_iter):
            yield {"event": "token", "data": token}
        # terminal grounding event — citations known up front, emitted after the prose
        sources = ChatSources(citations=citations, disclaimer=DISCLAIMER)
        yield {"event": "sources", "data": sources.model_dump_json()}

    return EventSourceResponse(events())
```

- **Events:** `event: token` frames carry text deltas; a single terminal `event: sources` frame carries
  `{citations, disclaimer}` JSON so the UI renders grounding after the answer.
- **Disconnect:** `EventSourceResponse` cancels the generator cleanly on client disconnect — we don't
  hand-own it.
- **No business logic here:** the route pulls tokens and citations from `core.chat_stream` and frames
  them. Grounding/citation logic stayed in `core/` (§1b).

> **Build note:** verify `iterate_in_threadpool` accepts the sync generator directly on the installed
> Starlette; if the token iterator is lazy (it is — `llm.stream` is a generator), wrapping is correct.

---

## 8. Step 7 — exception handlers + CORS

Map `core/` failures to HTTP honestly — a small set, no sprawl:

```python
# embedding-model mismatch / missing index (ValueError from the Retriever guard) → 500 with a clear msg
# upstream LLM error or refusal → 502 (bad upstream) — wrap the anthropic exception type
# Pydantic validation → 422 automatically (no handler needed)
```

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allow_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

> CORS is wired now even though local `make dev` is same-machine, because Phase 5 deploys UI and API to
> different hosts; doing it now avoids a confusing cross-origin failure later.

---

## 9. Step 8 — tests (`tests/test_api.py`, offline via the stub)

Extend the Phase 0 `TestClient` habit. The Seam-4 stub + the fixture corpus make it offline and free.

- **`/analyze` happy path:** override `get_llm` → `StubLLM(structured=<a valid ComplianceMemo>)`; POST a
  `Situation`; assert 200, a valid `ComplianceMemo`, disclaimer present.
- **`/analyze` validation:** POST a malformed body (e.g. `decision_domains: ["not_a_domain"]`); assert
  **422** with field detail.
- **`/chat` SSE:** override `get_llm` → `StubLLM(text="...")`; POST a `ChatRequest`; read the streamed
  body; assert `event: token` frames appear **and** a terminal `event: sources` frame whose JSON carries
  `citations` + `disclaimer`. (`TestClient` reads the streamed body; for SSE, iterate `response` or read
  `.text` and parse frames.)
- **`/health`:** asserts `core.corpus_size` is an int and `generation_model` is reported.
- **Override the retriever too** where useful: a small stub retriever avoids the fixture-corpus model
  download in unit tests; one test against the real fixture corpus confirms the wiring.
- **Live smoke (manual, gated):** extend `tests/test_live.py` with a `@pytest.mark.live` test that hits
  `/analyze` and `/chat` against real Haiku via `TestClient` with `llm_provider="anthropic"`. Not in CI.

Wire nothing new in `pyproject.toml` — the `live` marker + `addopts = "-m 'not live'"` from Phase 2
already gate it.

---

## 10. Step 9 — `make dev` & manual verification

`make dev` already boots both processes (`Procfile`: `uvicorn ... --reload --port 8000` + Streamlit).
No Procfile change. Manual check before calling it done:

```bash
curl -s localhost:8000/health | jq
curl -s -X POST localhost:8000/analyze -H 'content-type: application/json' \
  -d '{"jurisdictions":["Colorado"],"decision_domains":["employment"],"roles":["deployer"]}' | jq
curl -N -X POST localhost:8000/chat -H 'content-type: application/json' \
  -d '{"messages":[{"role":"user","content":"What must a Colorado deployer disclose?"}]}'
```

(The `/analyze` and `/chat` calls hit the stub unless `LLM_PROVIDER=anthropic` + a key are set.)

---

## 11. Step 10 — SPEC §8

Add the API wire contracts alongside the Phase 2 core shapes already there:
`ChatRequest` (`messages: list[Msg]`), the `/chat` SSE event protocol (`token` frames + terminal
`sources` frame), and `ChatSources` (`citations`, `disclaimer`). Note `/analyze` reuses `Situation` →
`ComplianceMemo` verbatim. Define once; the UI (Phase 4) serializes against these.

---

## 12. Intended build order (mirrors plan §11, corrected for §1)

1. `pyproject.toml` + `config.py` (`sse-starlette`, `cors_allow_origins`); re-freeze.
2. **Core touch-up (§1b):** `chat_stream` → `(citations, token_iter)`; fix Phase 2 `test_chat.py`; green.
3. `api/models.py` (`ChatRequest`, `ChatSources`, `HealthResponse`); reuse `Situation`/`ComplianceMemo`.
4. `api/main.py`: lifespan (retriever + laws + embedding_model into `app.state`) + `get_*` deps.
5. `GET /health` upgraded; `TestClient` shape test.
6. `POST /analyze` (sync) over `applicable_laws` → `generate_memo`; happy-path + 422 tests with the stub.
7. `POST /chat` async SSE over `chat_stream`; stream framing test; then a live-Haiku smoke check.
8. Exception handlers + `CORSMiddleware`.
9. SPEC §8; `make dev` boots; `curl` both endpoints; `make test` + `make lint` green; CI green.

---

## 13. Definition of done (from plan §2)

- [x] `POST /analyze` validates a `Situation` (422 on bad input), runs `applicable_laws` →
      `generate_memo`, returns a `ComplianceMemo` with the disclaimer.
- [x] `POST /chat` streams `token` SSE frames then a terminal `sources` frame (citations + disclaimer).
- [x] `GET /health` reports corpus size + embedding model + generation model.
- [x] Retriever + laws metadata load **once** at startup (lifespan), held in `app.state`, injected.
- [x] `LLMClient` injected via `get_llm`; tests swap `StubLLM` via `dependency_overrides` — fully offline.
- [x] `TestClient` tests pass offline (analyze happy + 422, chat SSE framing, health shape); CI green.
- [x] `CORSMiddleware` allows the configurable Streamlit origin.
- [x] `/analyze` + `/chat` wire contracts recorded in SPEC §8.

---

## 14. As-built notes (2026-06-18)

- **`sse-starlette` pinned at 3.4.4.** `EventSourceResponse` accepts an async generator yielding
  dicts; dict keys map directly to `ServerSentEvent` kwargs (`event`, `data`, `id`, `retry`).
  `ping` and `sep` kwargs confirmed present. `iterate_in_threadpool` from `starlette.concurrency`
  accepts the sync token generator correctly.
- **`chat_stream` core touch-up (§1b) confirmed.** Phase 2 streaming tests updated to unpack
  `(citations, token_iter)` — all 8 `test_chat.py` tests green, plus a new
  `test_chat_stream_returns_citations` test added.
- **`B008` added to ruff ignore list.** `ruff-bugbear` B008 fires on `Depends()` in default
  argument positions — this is the standard FastAPI pattern, not a bug. Added `"B008"` to
  `pyproject.toml` `[tool.ruff.lint] ignore`.
- **Lifespan does not run in offline unit tests.** Starlette's `TestClient` only runs the
  lifespan when used as a context manager (`with TestClient(app)`). Module-level
  `TestClient(app)` skips it — so all offline API tests use plain `TestClient(app)` and set
  `dependency_overrides` to inject stubs. The health endpoint uses
  `getattr(request.app.state, "embedding_model", None)` to tolerate the no-lifespan case.
- **`test_api.py` added:** health shape, `/analyze` happy + 422, `/chat` SSE token frames +
  terminal sources frame + ordering. All offline via `StubLLM` + `_StubRetriever`.

### Post-review hardening (Opus review, 2026-06-18)

A critical review after the initial build surfaced and fixed the following:

- **Finding 1 — Seam-4 boundary leak (fixed).** The first cut imported `anthropic` into
  `api/main.py` to catch the SDK's exception type — violating "only `core/llm.py` knows the
  provider." Fixed by adding **`core.LLMError`**: `AnthropicLLM` now wraps every SDK call
  (`complete`/`complete_structured`/`stream`) catching `anthropic.AnthropicError` and re-raising
  `LLMError`; the API catches `LLMError` → 502. No vendor SDK import remains in `api/`.
  `LLMError` is exported from `core/__init__.py`.
- **Finding 2 — default stub returned an invalid memo (fixed).** Default `StubLLM` (what
  `make dev` uses with no key) produced a `ComplianceMemo` via `model_construct()` missing
  `per_law` + `disclaimer`, which FastAPI serialized as a partial body — breaking invariant #4
  (disclaimer on every surface) for offline UI dev. `StubLLM.complete_structured` now returns a
  valid, chrome-complete `_default_memo()` for `ComplianceMemo`, carrying the real `DISCLAIMER`.
- **Finding 3 — `/chat` mid-stream errors (fixed).** Exception handlers can't map a failure once
  the SSE response has started (200 already sent). The `/chat` generator now catches `LLMError`
  during token iteration and emits a terminal **`event: error`** frame (`{"detail": ...}`); a
  stream ends with either `sources` (success) or `error` (failure), never both. Documented in
  SPEC §8.6.
- **Note 4 — LLM client built per request (fixed).** `get_llm` rebuilt the client (and its httpx
  pool) every request, contradicting the lifespan "load once" lesson. The client is now built once
  in lifespan into `app.state.llm`; `get_llm` reads it with a fresh-build fallback for the
  no-lifespan unit-test path.
- **Note: `/chat` blocking retrieval (fixed).** `chat_stream` does a blocking embed+retrieve up
  front; it now runs via `run_in_threadpool` so the async route doesn't block the event loop
  (pre-stream errors still map to HTTP codes).
- **Note 5 — vestigial `ValueError → 500` handler (documented).** Its main intended trigger
  (embedding mismatch) fails at startup, not per request; kept as a safety net with a comment.
- **Note 6 — SSE multi-line `data` (documented in SPEC §8.6).** Real token deltas contain
  newlines; the Phase 4 Python SSE client must rejoin multi-line `data:` lines.
- **Note 7 — exception breadth (resolved).** `AnthropicLLM` catches `anthropic.AnthropicError`
  (the SDK root), not just `APIError`, so all provider failures wrap into `LLMError`.
