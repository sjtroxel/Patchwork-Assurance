# Observability — ops note

How to read Patchwork's structured logs and cost data (Phase 7). One page; the design rationale lives in
`docs/roadmap/phase-7-observability-security.md`.

## Where the logs are

Structured **JSON, one event per line, to stdout** (no hosted tool — stdlib logging). On Railway, that's
the service's live logs. Locally, it's your terminal. Toggle with `LOG_LEVEL` (default `INFO`) and
`ENABLE_TRACING` (default `true`).

## The privacy rule (so the logs are safe)

Every line is **metadata only** — `request_id`, stage, latency, token counts, cost, model. The logs
**never** contain user inputs, retrieved statute text, or generated output. That's enforced in code and
asserted by a test (a sentinel input never appears in any log line). So the logs are safe to read, share,
and retain without touching the "we don't store your inputs" promise.

## Correlate one request

Every line carries a `request_id`. The API assigns one per request (or honors an inbound `X-Request-ID`)
and echoes it back as a response header. To see everything one request did:

```
grep '"request_id": "<id>"' logs.txt
```

That gives you the request's retrieval, its LLM call(s), and any guard flags, in order.

## The event types

| `event` | When | Key fields |
|---|---|---|
| `llm_call` | one per model call (Seam 4) | `surface` (`complete`/`complete_structured`/`stream`/`…:error`), `model`, `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`, `latency_ms`, `est_cost_usd`, `known_rate` |
| `retrieve` | one per retrieval | `k`, `n_results`, `jurisdiction`, `latency_ms` (never the query text) |
| `grounding_guard` | output cited a section that isn't real | `surface` (`memo`/`chat`), `unresolved` (count), `citations` (the bad section tokens) |
| `corpus_injection_flag` | at ingest, instruction-like text in a corpus doc | `law_id`, `section`, `n_flags`, `phrases` |

## Reading cost

- `est_cost_usd` on each `llm_call` is computed in `core/pricing.py` from the four token tiers. **The
  tiers are additive** — `input_tokens` is only the *uncached* remainder — so don't read it as the whole
  prompt. Rates are pinned in one place (re-verify at build; they churn).
- A per-process **rolling total** is available via `obs.cost_summary()` (calls, cost, tokens; resets on
  restart — stateless by design).
- **Cache signal:** if `cache_read_tokens` is consistently `0`, the stable statute prefix isn't being
  cached — every request re-pays full input price on a large identical prefix (a cheap optimization to
  revisit).

## What to watch

- **Any `grounding_guard`** — the output cited a section not in the corpus. Usually a model slip; on the
  chat surface it can be the *effect* of an injection. Worth a look. (It logs + flags; it does not block —
  on streamed chat the reply is already sent.)
- **Any `corpus_injection_flag`** — a corpus document contains instruction-like text. On the v1
  human-curated corpus this should never fire; it's the rail for the Phase 9 auto-write agent. Review
  before trusting that document.
- **`est_cost_usd` / `latency_ms` outliers** — a slow or expensive request; the `request_id` ties the
  cost to the retrieval + generation that produced it.
- **`known_rate: false`** on an `llm_call` — a model id without a pinned rate (cost shows `0`); add it to
  `core/pricing.py`.

## Note

The real per-request cost numbers come from a live request (`LLM_PROVIDER=anthropic`), so they ride the
same paid-run timing as the Phase 6 judged eval — the instrumentation is in place; the *numbers* land
when a real request runs. Also confirm on the live box that `request_id` propagates into the threadpool
LLM call (the unit tests are same-thread; see the Phase 7 IMPLEMENTATION §0 note).
