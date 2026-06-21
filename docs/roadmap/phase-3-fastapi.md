# Phase 3 — FastAPI

*Phase plan (intended design), written 2026-06-17. Part of the phase spine in
[`../ROADMAP.md`](../ROADMAP.md) §6. Wraps the Phase 2 `core/` functions in an HTTP API: `/analyze` and
`/chat` with Pydantic request/response models and SSE streaming for chat. Imports `core/`; `core/` never
imports it (the keystone rule). The request/response shapes are the API half of `docs/SPEC_V1.md` §8.
Streaming specifics verified against the Anthropic API skill on 2026-06-17. The as-built companion
`phase-3-fastapi-IMPLEMENTATION.md` is written when the phase begins.*

---

## 1. What Phase 3 is

A thin, typed HTTP shell over logic that already works.

Phase 2 built and tested the brain with no web layer. Phase 3 exposes it: `POST /analyze` returns a
structured `ComplianceMemo`, `POST /chat` streams a grounded conversational answer over SSE, and the
Phase 0 `/health` becomes a real readiness check. The API is deliberately **thin** — it validates input,
calls a `core/` function, and serializes the result. No business logic lives here; if a rule about
scope or grounding is in `api/`, it is in the wrong layer.

This is the single path multiple consumers will hit: the Streamlit UI (Phase 4) now, the eval harness
(Phase 6) and the v2 monitoring agent (Phase 9) later (ROADMAP §3). Getting it right — one typed
contract, one streaming surface — is why FastAPI earns its place beyond the résumé signal.

**Primary learning (ROADMAP §6):** FastAPI, async, and SSE (the backend rep).

---

## 2. Definition of done

- [x] `POST /analyze` accepts a `Situation` (Pydantic-validated), calls `core.generate_memo`, and
      returns a `ComplianceMemo`. Bad input is a 422 (Pydantic), not a 500.
- [x] `POST /chat` streams a grounded answer over **SSE**: token deltas as they arrive, then a final
      event carrying the citations/sources and the disclaimer.
- [x] `GET /health` reports real readiness (corpus size, embedding model, generation model) — the
      Phase 1 `corpus_size` plus the model wiring.
- [x] The embedding model + Chroma collection load **once at startup** (FastAPI lifespan), held in app
      state and injected — never reloaded per request.
- [x] The `LLMClient` is injected via a dependency, so tests swap in the Phase 2 `StubLLM` with
      `app.dependency_overrides` — the whole API is testable with no network and no API key.
- [x] `TestClient` tests pass offline: `/analyze` happy path + validation error, `/chat` yields SSE
      events, `/health` shape. CI green.
- [x] CORS is configured so the Streamlit origin can call the API (needed once they deploy to different
      hosts in Phase 5).
- [x] The `/analyze` and `/chat` request/response contracts are recorded in `docs/SPEC_V1.md` §8.

Done = the two real endpoints work end to end against the stub and against live Haiku, tested. No UI;
that's Phase 4.

---

## 3. Explicitly NOT in Phase 3

- **No Streamlit, no UI.** Phase 4. The API is exercised by `TestClient` and `curl`/HTTPie here.
- **No deploy, no secrets management beyond `.env`.** Phase 5. Runs locally via `make dev`.
- **No new `core/` logic.** If a behavior is missing, it belongs in `core/` (Phase 2), not bolted into a
  route. The API only transports.
- **No auth, no rate limiting, no persistence** (ROADMAP §8). Stateless: `/chat` takes the full history
  in the request body; the server stores nothing.
- **No evals, observability, or hardening.** Phases 6–7.

---

## 4. The endpoints

Three routes in `api/`, all thin over `core/`.

- **`GET /health`** — readiness, not a pinned contract. Returns `{api, core: {corpus_size,
  embedding_model}, generation_model}`. Extends the Phase 0/1 health with the model wiring so a deploy
  smoke-test (Phase 5) can confirm the index and models are live.
- **`POST /analyze`** — the demoable surface. Body: `Situation`. Calls `core.generate_memo(situation,
  llm, retriever)`. Returns `ComplianceMemo`. A **sync `def`** endpoint — FastAPI runs it in a
  threadpool, so the CPU-bound embedding/retrieval and the blocking LLM call don't stall the event loop
  (§6 explains why sync is correct here).
- **`POST /chat`** — the flexible surface. Body: `ChatRequest` (`messages: list[Msg]`, stateless full
  history). Returns an **SSE stream** (§6): the grounded answer token-by-token, then a final `sources`
  event. Wraps `core.chat`'s token iterator.

---

## 5. Pydantic request/response models — the API contract

FastAPI is Pydantic-native, so the SPEC §8 shapes become the wire contract directly.

- Request models: `Situation` (for `/analyze`), `ChatRequest` (for `/chat`).
- Response models: `ComplianceMemo` (declared as the route's `response_model`), and for `/chat` the
  streamed text plus a terminal `ChatSources` payload (citations + disclaimer).
- These reuse the Phase 2 `core/` schemas where possible — the same Pydantic models, imported, so the
  API contract and the core contract cannot drift. Record the final wire shapes in `SPEC_V1.md` §8.
- Validation is free and load-bearing: a malformed `Situation` returns a **422** with field detail, not
  a 500 — input errors are the client's fault and should read that way.

---

## 6. SSE streaming for `/chat` — the async rep, without making `core/` async

The honest tension and its clean resolution:

- **`core/` is synchronous** (sentence-transformers and Chroma are sync/CPU-bound; the Anthropic SDK's
  `messages.stream(...).text_stream` is a sync iterator — verified 2026-06-17). Making `core/` async
  would be churn for no gain.
- **SSE wants an async response.** Bridge the two: `core.chat` yields a **sync** `Iterator[str]` of
  token deltas (built on `LLMClient.stream`, Phase 2 §8); the `/chat` endpoint is `async` and adapts
  that sync iterator into the async streaming response using Starlette's `iterate_in_threadpool` (ships
  with FastAPI — no new dependency), so the blocking token pulls happen off the event loop.
- **Format:** each token is an SSE `data:` frame; a terminal named event (`event: sources`) carries the
  citations + disclaimer JSON so the UI can render grounding after the prose. On client disconnect the
  generator is cancelled cleanly.
- **Library (decided 2026-06-17): `sse-starlette`'s `EventSourceResponse`** — purpose-built, handles
  keep-alive pings, disconnects, and SSE framing correctly, so those edge cases aren't hand-owned. One
  small dependency, accepted. (The hand-rolled `StreamingResponse` with `media_type="text/event-stream"`
  was the no-dep alternative.)

This is the FastAPI/async/SSE learning, on the real product path rather than a toy.

---

## 7. App wiring — load once, inject everywhere

The structural FastAPI lessons live here.

- **Lifespan startup.** The embedding model and the persistent Chroma collection are expensive to load;
  do it **once** in a `lifespan` context manager, store the retriever in `app.state`. Per-request model
  loading would make every call slow — this is the difference between a usable API and a toy.
- **Dependency injection.** `get_retriever()` pulls the retriever from `app.state`; `get_llm()`
  constructs the `LLMClient` from config (`anthropic` | `stub`). Routes depend on these via `Depends`.
- **Why injection matters for tests:** `app.dependency_overrides[get_llm] = lambda: StubLLM()` makes the
  entire API run offline and deterministically in CI (§10). This is the payoff of the Phase 2 Seam 4
  interface meeting FastAPI's DI.

---

## 8. Error handling and CORS

- **Map `core/` failures to HTTP honestly:** Pydantic validation → 422 (automatic); the
  embedding-model-mismatch guard (Phase 1 §6.3) or a missing index → 500 with a clear message; an
  upstream LLM error/refusal → 502/503. A small set of exception handlers, no sprawl.
- **The disclaimer rides in the payload**, not just the UI: `ComplianceMemo.disclaimer` and the `/chat`
  terminal `sources` event both carry the not-legal-advice line, so even a raw API consumer gets it
  (ROADMAP §5, §9; `.claude/rules/legal-content.md`).
- **CORS:** add `CORSMiddleware` allowing the Streamlit origin (configurable). Local `make dev` is
  same-machine, but Phase 5 deploys UI and API to different hosts, so wire it now to avoid a confusing
  cross-origin failure later.

---

## 9. Config and dependencies added this phase

**Config additions** (`config.py`): `cors_allow_origins` (default the local Streamlit origin);
everything else (`api_base_url`, model names, paths) already exists from Phases 0–2.

**Dependencies:** `fastapi` and `uvicorn` are already present (Phase 0). Add **`sse-starlette`** for
`/chat` (decided §6). Pin the version in IMPLEMENTATION.

---

## 10. Testing

Extends the Phase 0 `TestClient` habit; the Seam 4 stub makes it offline and free.

- **`/analyze`:** happy path returns a valid `ComplianceMemo` (stub LLM via `dependency_overrides`); a
  malformed `Situation` returns 422 with field detail.
- **`/chat`:** the SSE stream yields token events and a terminal `sources` event; assert the framing and
  that the disclaimer is present. (`TestClient` can read the streamed body.)
- **`/health`:** reports `corpus_size` and the model wiring.
- **No network, no key in CI** — the override swaps in `StubLLM`; the retriever runs against the Phase 1
  fixture corpus. A couple of live-Haiku smoke tests stay behind the env-flag marker (Phase 2 §12),
  manual only.

---

## 11. Intended build order

1. Pydantic request/response models in `api/` (reusing `core/` schemas); pin the shapes in `SPEC_V1.md`
   §8.
2. Lifespan startup loading the retriever into `app.state`; `get_retriever()` / `get_llm()`
   dependencies.
3. `GET /health` upgraded to report corpus size + model wiring.
4. `POST /analyze` (sync `def`) over `core.generate_memo`; `TestClient` tests with the stub override
   (happy path + 422).
5. `POST /chat` async SSE over `core.chat`'s token iterator (the `iterate_in_threadpool` bridge);
   stream tests; then a live-Haiku smoke check.
6. Exception handlers + `CORSMiddleware`.
7. Confirm `make dev` boots and the UI-less API answers `curl`/HTTPie for both endpoints; CI green.

---

## 12. Open decisions for this phase

- **SSE library.** ~~Open~~ **Decided 2026-06-17: `sse-starlette`** (`EventSourceResponse`) — see §6.
- **Sync `def` vs `async def` for `/analyze`.** Recommend sync `def` (threadpooled) since `core/` is
  sync; revisit only if a future async core path appears.
- **How much of the memo to stream.** v1 streams only `/chat`; `/analyze` returns the whole
  `ComplianceMemo` at once (it's structured, not prose). Streaming the memo is a possible later polish,
  not v1.
- **Terminal `sources` event shape.** Settle the exact `/chat` sources payload when wiring it; record in
  SPEC §8.

---

## 13. What this hands forward

- **To `docs/SPEC_V1.md` §8:** the `/analyze` and `/chat` request/response wire contracts (alongside the
  Phase 2 core schemas they reuse) — the single source of truth the UI serializes against.
- **To Phase 4 (Streamlit):** two stable endpoints behind `settings.api_base_url` — the memo form
  `POST`s a `Situation` to `/analyze`; the chat page consumes `/chat`'s SSE stream. The UI stays thin
  because the API already does the work.
- **To Phase 6 (evals):** the eval harness can hit the same `/analyze` path the app uses, or import
  `core` directly — either way it exercises production logic, not a parallel copy.
- **To Phase 9 (agent):** the monitoring agent is another consumer of this same API surface.
