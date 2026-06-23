# Phase 7 — IMPLEMENTATION (observability & security)

*As-built runbook, written at phase start (2026-06-23), reflecting how Phases 0–6 actually landed. The
intended design + threat model live in `phase-7-observability-security.md` (read it first); this doc
records the resolved decisions and the build specifics. Phase 7 is unblocked (the binding-rule-1 gate
lifted at v1); Phase 6's one deferred paid run does not block it. Cadence unchanged: Opus scaffolds;
**sjtroxel runs all terminal + git**.*

*Budget note: the builder is pacing tokens (subscription weekly limit) and API credit ($0.31 until next
week). Phase 7 is **$0 by design** — structured logging + the `usage` object + deterministic guards. No
hosted observability tool, no per-request judge call. Verify any new dep/version at build (standing rule).*

---

## 0. Verified-at-build facts (confirm before relying on them)

- **Seam 4 is the instrumentation point.** `core/llm.py:AnthropicLLM` is the *only* module that imports
  `anthropic`, so it is the one place the provider `usage` object exists. Instrument there, not in a
  generic Protocol decorator (the Protocol methods return `str`/parsed/iterator and have already thrown
  the `usage` away).
- **The `usage` object** (re-verify at build): `input_tokens`, `output_tokens`, `cache_creation_input_tokens`,
  `cache_read_input_tokens`. On non-stream calls it's `resp.usage`; on `stream` it arrives on the final
  message (`stream.get_final_message().usage`) / `message_delta`.
- **Runtime models are Haiku (chat) + Sonnet (memo)** at $1/$5 and $3/$15 per 1M (in/out); Opus ($5/$25)
  is judge-only (eval, not the request path). Re-confirm rates at build.
- **Phase 6 already built the grounding primitives** — `locate_section`, `corpus_section_texts`, the
  citation-exists check (currently in `eval/`). Phase 7 reuses them as a *runtime* guard, which forces a
  small refactor: lift them into `core/` (§7) so the API and the eval share one path (the keystone
  invariant — everything through `core/`; `eval` may import `core`, never the reverse).
- **The not-legal-advice posture is already partly hardened:** the law-facts card is labeled
  "authoritative background, **not** a citable source," the chat declines out-of-corpus questions, and the
  disclaimer is structural (rides in the payload, not model-generated). Phase 7 formalizes + tests this,
  it doesn't start from zero.
- **HARD RULE — logs never contain user content.** Statelessness/privacy is an invariant ("we don't
  store your inputs", ROADMAP §8, invariant 3). The observability logs record **metadata only**:
  `request_id`, `stage`, `latency_ms`, the token counts, `est_cost_usd`, `model`. They **never** record the
  user's situation text, chat messages, retrieved chunk text, or generated output — at most a character
  length or a hash, never the content. Logging request/response bodies would silently break the privacy
  posture and manufacture exactly the retention surface the app promises not to have. This rule is a
  reviewable line item in every logging PR for this phase.
- **ContextVar → threadpool propagation (verify at build).** The API runs LLM calls off the event loop via
  `run_in_threadpool` / `iterate_in_threadpool` (Starlette/anyio). The `request_id` `ContextVar` set in the
  async request must reach the worker thread, or the Seam-4 log lines lose correlation. anyio's
  `to_thread.run_sync` copies the context by default — **confirm the `request_id` actually appears in a
  Seam-4 log line** during the build; if it doesn't, capture it in the dependency and pass it explicitly
  rather than relying on the contextvar.

---

## 1. Resolved decisions (the plan's open items, decided)

- **Observability = structured-logging-only.** `structlog`-style JSON logs to stdout (Railway captures
  stdout), $0, local, teaches the fundamentals. **No hosted tool** (Langfuse/Logfire/Phoenix) for this
  phase — budget, and the fundamentals are the learning. A tracing UI stays an optional later add; the
  logs are already the source of truth.
- **Request correlation via a `contextvar`, not signature threading.** A FastAPI middleware assigns a
  `request_id` and sets it in a module-level `ContextVar`; the Seam-4 logger reads it. No `core` function
  signature changes — the dependency arrow stays clean.
- **Cost rates isolated in one spot** (`core/pricing.py`: `{model: (in_per_1m, out_per_1m)}` + a
  `cost(model, usage)` helper). Rates churn — one place to update, never scattered.
- **Runtime grounding guard = citation-exists on the OUTPUT TEXT (deterministic, FREE).** Parse the
  section citations the model wrote *into its output* (memo obligation citations; chat reply prose) and
  check each against the real corpus section index — catching a hijack *by its effect* (it cites a fake /
  no real section) for $0 and ~no latency. **Per-surface, this is not symmetric, and the doc must not
  pretend it is:**
  - **Memo (strong):** the model authors citations into structured output; a fabricated citation is caught.
  - **Chat (partial):** the `ChatTurn.citations` list is **retrieval-derived and therefore always real** —
    checking *it* proves nothing. The guard must parse cited sections from the **reply text**, and because
    chat **streams**, that check is **post-stream** (the reply has already been sent → log/flag only, never
    block). And a chat hijack that simply avoids citing a fake section won't trip it at all. So on chat,
    citation-exists is a **necessary-but-insufficient** backstop; the real chat defense is the prompt-side
    layer (instruction hierarchy, delimiting, meta-request refusal) plus the structural disclaimer (§4).
    Defense in depth — no single layer is trusted.
- **Groundedness-via-judge is NOT used per request** (it would add an Opus call = cost + latency to every
  turn); it stays the offline eval metric. (If a stronger live chat guard is ever wanted, it's a judged
  call behind a flag — a deliberate cost decision, not a default.)
- **Guard failure mode = log + flag, not block (v1.x).** Withholding on a guard miss risks dropping valid
  answers on a false positive — and on streamed chat, blocking is impossible anyway (already sent). Log it,
  flag it in the response metadata, revisit blocking (for the non-streamed memo path) once real miss-rates
  are visible (plan §12 open item, decided conservative).

---

## 2. Observability — build

1. **Structured logger** (`core/logging.py` or `core/obs.py`): a thin JSON logger (pin `structlog` at
   build; confirm it isn't already a dep). One event per stage with `request_id`, `stage`, `latency_ms`.
2. **Request-ID middleware** (`api/main.py`): read an incoming `X-Request-ID` header if the UI set one
   (true end-to-end correlation across the UI↔API hop), else generate a uuid4; set the `ContextVar`; echo
   it back as a response header. `ui/client.py` can generate + send the header so a Streamlit interaction
   and its API call share one ID.
3. **Seam-4 usage + latency capture:** wrap each `AnthropicLLM` method (`complete`/`complete_structured`/
   `stream`) to time the call and emit ONE **metadata-only** log line (no prompt/response content — §0)
   with `model`, the four `usage` fields, `latency_ms`, and `est_cost_usd` (§3). `StubLLM` emits a
   zero-cost synthetic line so offline/CI traces are complete and free. For `stream`, `usage` is on the
   final message (`get_final_message().usage`); on a **mid-stream `LLMError`** (the SSE response has
   already started — Phase 3 §caveat, can't become a clean 502) log the partial output-token count + the
   error so an interrupted/expensive stream is still visible.
4. **Stage timing in `core`:** time embedding/retrieval vs generation separately (log lines in the
   retrieve + generate paths) so a slow request is diagnosable — and so cold-first-request warm-up
   (container restart/redeploy) is visible even though Railway is always-on.

## 3. Cost / usage

- `core/pricing.py`: current per-1M rates (Haiku, Sonnet; Opus for completeness) + a `cost(model, usage)`
  helper. **Exact formula, and the gotcha:** the four usage fields are **additive** — total prompt tokens =
  `input_tokens + cache_read_input_tokens + cache_creation_input_tokens`, where `input_tokens` is only the
  **uncached remainder**. So bill each tier at its own rate and do not double-count:
  `cost = (input_tokens·in + output_tokens·out + cache_read·in·0.1 + cache_creation·in·1.25) / 1e6`
  (5-min cache write = 1.25×; verify the multipliers at build). Naively using `input_tokens` as the whole
  prompt underbills a cached request and overstates the cache win — get this right or the numbers lie.
- Log `est_cost_usd` per call; a tiny rolling aggregator (in-memory, stateless — counts/sums only, resets
  on restart, consistent with invariant 3) for a per-process running total. This keeps the "pennies per
  memo" claim (ROADMAP §7) honest with real numbers.
- **Caching signal to watch:** if `cache_read_input_tokens` is consistently **0** across requests, the
  stable statute-context prefix (law-facts card + system prompt, Phase 2 §9) is **not** being cached — i.e.
  every request re-pays full input price on a large, identical prefix. The instrumentation surfaces this;
  the fix (add `cache_control` to the stable prefix) is a cheap cost win worth noting as a finding, though
  the wiring itself can be a small follow-up rather than core Phase 7 scope.

## 4. Security — what exists vs what to build

**Two surfaces (plan §6):** direct injection (chat) and indirect injection (poisoned corpus). v1's corpus
is human-curated official statute text, so indirect risk is low *today* — but **Phase 9's agent
auto-writes to `corpus/`**, so the loader defense must exist before then. Build now:

- **Delimit + label untrusted content in the prompts.** Wrap user input and retrieved chunks in explicit
  delimiters (e.g. fenced `<user_input>…</user_input>` / `<retrieved_statute>…</retrieved_statute>`
  blocks) in `core/prompts.py`, with a system-prompt line stating that anything inside is reference DATA,
  never instructions. The facts card is already labeled authoritative-not-citable; extend the discipline
  to user + chunk text. **Honesty: prompt-level delimiting is necessary but defeatable** — a determined
  injection can still talk past it. That is *why* the robust layer is the **structural disclaimer** (it
  rides in the payload, not the model's choice) plus the **output-side guard** (§1): we defend by effect,
  not by trying to enumerate attack strings. Delimiting raises the bar; it is not the whole wall.
- **Refuse meta-requests — but calibrated, so legitimate questions still get answered.** Hostile
  meta-requests ("print your system prompt", "ignore the disclaimer", "you are now…") → grounded refusal,
  disclaimer kept. **The trap to avoid is over-refusal:** a real user asking "what does the statute
  *require* about disclosure?" or "what are my obligations?" is a legitimate, in-scope question, not an
  attack — it must still be answered. The distinction is *operator-authority override / exfiltration* vs
  *substantive statutory question*. The regression set (§7) therefore includes **false-positive cases**:
  legitimate statutory questions asserted to still get a grounded answer, not a refusal.
- **Runtime citation-exists guard** (§1) on `/chat` and `/analyze` output: a hijacked answer typically
  cites no real section → log + flag.
- **Loader provenance + sanitization** (`core/corpus/loader.py`): `source_url` is already recorded;
  add a lightweight pass that flags instruction-like content in ingested chunks for human review. The
  **human gate** on corpus changes (ROADMAP §5) is itself the load-bearing control for Phase 9.

## 5. The grounding refactor (Phase 6 synergy, done right)

Lift `locate_section` + `corpus_section_texts` + the citation-exists check from `eval/harness.py` /
`eval/metrics.py` into **`core/grounding.py`**. Then:
- `eval/` imports them from `core` (offline metric) — unchanged behavior, fixes the layering.
- `api`/`core` import them as the runtime guard.
"Build it once in Phase 6, deploy two ways" (plan §8) — but the shared code must live in `core`, since
`core` can't import `eval`. Small, mechanical move; keep the existing tests green through it.

**One genuinely new piece** (eval didn't need it): the offline metric checked *structured* citation
fields, but the runtime chat guard must pull section references out of **free model prose**. Add a
`cited_sections(text) -> list[str]` parser to `core/grounding.py` that extracts section-like tokens
(CO `6-1-1704`, CT `Sec. 9`) from output text, then runs each through `locate_section`. Reuse the
boundary-guarded matcher (the `(?!\d)` guard so `Sec. 9` ≠ `Sec. 10`). Unit-test the parser on real and
fabricated prose — it is the load-bearing new code, so it gets the most test attention.

## 6. Config + dependencies

- **Config:** `log_level: str = "info"`, `enable_tracing: bool = True` (toggles the structured logs).
- **Deps:** likely just `structlog` (pin at build; confirm not already present). No observability SDK.

## 7. Testing

- **Injection regression set** (security tests in `tests/` — distinct from the `eval/gold` *correctness*
  set). Attack messages: prompt override, system-prompt exfiltration, disclaimer-drop, poisoned-chunk.
  Assertions: the disclaimer is present, **no system-prompt text leaks into the output**, and the output
  stays grounded (no fabricated section via the parser). **Plus false-positive cases:** legitimate
  statutory questions ("what does the statute require about disclosure?") asserted to still get a grounded
  answer, not a refusal (guards against over-refusal, §4).
  - **HONESTY about what a stub can and can't test (do not let a green suite create false confidence).**
    `StubLLM` returns canned text regardless of the attack, so the offline suite verifies the *deterministic*
    layer only: the disclaimer rides the payload, the prompt assembles with the delimiters, and the
    output-side guard/parser runs and flags. It **cannot** verify that *the model resists* an injection —
    that is a **live-model check** behind the `live` marker, run when credits allow. The deterministic
    suite locks the chrome + guard wiring; the model's actual injection-resistance is a separate,
    explicitly-flagged live test, not something the stub proves.
- **Usage-capture test:** assert the Seam-4 wrapper records the four token fields + a cost, that a request
  emits a complete trace (request_id at each stage), **and that the emitted log lines contain NO user
  input or model output text** (the §0 privacy rule, asserted by test — e.g. a known sentinel string in
  the input never appears in any log record). `StubLLM` path, offline.
- **Loader-poisoning test:** a fixture doc with embedded instructions is ingested; assert it's flagged /
  quoted and a query over it doesn't produce the injected behavior.

## 8. Build order

1. Structured logging + request-ID middleware + the Seam-4 usage/latency wrapper.
2. `core/pricing.py` + cost logging + the rolling total.
3. The `core/grounding.py` refactor (§5), then wire the citation-exists runtime guard into `/chat` + `/analyze`.
4. Prompt hardening (delimiters + meta-request refusal) + the injection regression set.
5. Loader provenance/sanitization + the poisoned-document test.
6. Ops note (how to read a trace + the cost log).

## 9. Open decisions remaining (small, decide at build)

- **Hosted tracing UI later?** Default no (budget). Revisit only if the logs prove insufficient.
- **Cost-rate source:** hardcode in `core/pricing.py` for now (one spot); fetching is overkill.
- **Guard blocking threshold:** start log-only; tune once real miss-rates are visible.

## 10. As-built notes

*(Fill during the build: the structured-logging dep/version pinned; the exact trace shape + a sample line;
the `core/grounding.py` move; the injection regression cases that pass; the loader-sanitization approach;
and the first real cost numbers from a live request — the "pennies per memo" claim, measured.)*
