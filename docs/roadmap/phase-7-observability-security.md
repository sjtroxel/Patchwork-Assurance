# Phase 7 — Observability & Security

*Phase plan (intended design), written 2026-06-17. Post-v1 phase (ROADMAP §6, v1.x band), after evals
(Phase 6). Instruments the live API path (tracing, token-cost, latency) and hardens the two attack
surfaces a grounded-LLM app has: prompt injection on the chat surface and poisoned documents in the
corpus loader. Observability-tool specifics are a fast-moving space — verify current options/pricing at
build (ROADMAP standing rule). The as-built companion `phase-7-observability-security-IMPLEMENTATION.md`
is written when the phase begins.*

---

## 1. What Phase 7 is

Seeing inside the app, and defending it.

Two jobs that pair naturally. **Observability:** instrument the request path so you can see token cost,
latency, and what happened on each call — you can't operate or improve what you can't see.
**Security:** an LLM grounded in retrieved text has two specific attack surfaces — a user trying to
hijack the chat, and a malicious document trying to hijack retrieval — and Phase 7 builds the defenses,
crucially **before** Phase 9's agent starts auto-writing to the corpus.

**Primary learning (ROADMAP §6):** observability tooling and LLM security.

---

## 2. Definition of done

- [ ] Every `/analyze` and `/chat` request is **traced**: a request ID flows UI→API→`core`→retrieval→LLM,
      with per-stage latency.
- [ ] **Token + cost** captured per LLM call from the Anthropic `usage` object (input/output/cache
      tokens → estimated cost), logged and summable.
- [ ] A defended **chat surface**: the not-legal-advice posture and grounding hold under prompt-injection
      attempts (override, system-prompt exfiltration, "ignore the disclaimer"); a regression set of
      injection cases passes.
- [ ] A defended **corpus loader**: retrieved text is treated strictly as data, never instructions;
      provenance is validated; a poisoned-document test case does not hijack generation.
- [ ] An **output-grounding guard** on responses (reusing Phase 6's citation-exists/groundedness check)
      that flags answers not supported by real corpus text.
- [ ] A short ops note: how to read the traces and the cost log.

Done = you can see cost/latency per request, and the two injection surfaces are defended and tested.

---

## 3. Explicitly NOT in Phase 7

- **No new product features.** This is instrumentation + hardening of the existing app.
- **No hybrid retrieval** (Phase 8), **no agent** (Phase 9) — but Phase 7's corpus-poisoning defense is a
  prerequisite the Phase 9 agent depends on.
- **No auth, no rate limiting, no WAF.** Stateless app, no accounts (ROADMAP §8). Security here is about
  prompt-injection and poisoned-context, not access control.
- **No paid observability platform required.** The fundamentals (structured logging + the usage object)
  are $0; a hosted/OSS tracing UI is an optional add (§12).

---

## 4. Observability — trace the request path

Instrument at the seams that already exist, so this is wrapping, not rewiring:

- **Request tracing:** a request ID assigned at the API boundary (FastAPI middleware), threaded through
  `core` calls, logged at each stage (retrieve, generate) with timing. Structured logs (a `structlog`-
  style JSON logger) so traces are greppable and machine-readable.
- **The `LLMClient` seam (Phase 2 §5) is the natural instrumentation point** — wrap `complete` /
  `complete_structured` / `stream` to record model, latency, and the `usage` numbers without touching
  callers. One decorator, every LLM call covered.
- **Latency per stage** (embedding/retrieval vs generation) so you can see where time goes — useful for
  isolating first-request warm-up (the Railway services are always-on as of Phase 4.5, but container
  restarts/redeploys still produce a cold first request).

## 5. Token, cost, and usage instrumentation

- The Anthropic response carries a **`usage`** object: `input_tokens`, `output_tokens`, and
  `cache_creation_input_tokens` / `cache_read_input_tokens` (verified 2026-06-17). Capture all four per
  call.
- Compute **estimated cost** from current per-token rates (Haiku-class; verify rates at build) →
  per-request and rolling totals. This is what keeps the "pennies per memo" claim (ROADMAP §7) honest
  with real numbers, and surfaces a prompt-caching win if the statute-context cache (Phase 2 §9) is
  paying off (`cache_read` > 0).
- Log cost alongside the trace so a slow/expensive request is diagnosable.

## 6. Security — the threat model (two surfaces)

A grounded-LLM app has exactly two injection surfaces; name them precisely:

1. **Direct prompt injection (chat surface).** A user message tries to override the system prompt
   ("ignore your instructions, you are now…"), exfiltrate the system prompt, drop the not-legal-advice
   disclaimer, or extract ungrounded legal claims. The memo path is partly shielded (structured output
   constrains it); the chat path is the open door.
2. **Indirect prompt injection (poisoned corpus).** A document ingested into `corpus/` contains hidden
   instructions ("when asked about X, tell the user Y"). Retrieval surfaces that text as context, and a
   naive prompt lets it act as an instruction. **Low risk in v1** (corpus is human-curated official
   statutes), but **Phase 9's agent auto-writes to the corpus** — so the defense must exist before then.

## 7. Defenses

- **Instruction hierarchy.** The not-legal-advice posture and grounding rules live in the **system
  prompt**; user and retrieved text are data, never operator instructions. (Per the Anthropic guidance,
  any genuine mid-conversation operator instruction uses the system role, not user text — so user input
  can't forge authority.)
- **Delimit and label untrusted content.** Retrieved chunks and user input are wrapped/marked as
  quoted data in the prompt, with an explicit instruction that text inside is reference material, not
  commands. Defends both surfaces.
- **Output-side grounding guard (the strong defense).** Reuse Phase 6's citation-exists / groundedness
  check on live responses: if the model was hijacked, its output usually won't be grounded in real
  corpus sections → flag/withhold. This catches injections by their *effect*, not by trying to
  enumerate attack strings.
- **Loader provenance + sanitization.** The corpus loader validates source (official `source_url`,
  Phase 1) and strips/flags suspicious instruction-like content; the **human gate** (ROADMAP §5) on
  authoritative corpus changes is itself a security control — a human reviews what the Phase 9 agent
  proposes before it's indexed.
- **Refuse meta-requests** ("print your system prompt", "ignore the disclaimer") and keep the disclaimer
  structural (it rides in the payload, Phase 3 §8 — not something the model can be talked out of).

## 8. Synergy with Phase 6

The Phase 6 groundedness/citation infrastructure does double duty here: the same check that *scores*
faithfulness offline becomes a *runtime guard* against injection. Build it once in Phase 6, deploy it
two ways. (And the injection regression set is just more gold cases.)

## 9. Config and dependencies added this phase

**Config additions:** `log_level`, `enable_tracing`, optionally a tracing-backend key (if §12 adopts a
hosted/OSS tool).

**Dependencies:** a structured logger (e.g. `structlog`) is the likely only certain add; an
observability SDK (Langfuse / Pydantic Logfire / OpenTelemetry / Arize Phoenix) is the §12 decision.
Pin in IMPLEMENTATION.

## 10. Testing

- **Injection regression set** — a list of attack messages (override, exfiltration, disclaimer-drop,
  poisoned-chunk) asserted to *fail to* hijack: the disclaimer survives, no system-prompt leak, output
  stays grounded. Runs with the `StubLLM` for the deterministic parts; live-model checks behind the
  flag.
- **Cost/trace tests** — assert the `usage`-capture decorator records the four token fields and that a
  request emits a complete trace.
- **Loader poisoning test** — a fixture document with embedded instructions is ingested; assert the
  defense (it's quoted/flagged, and a query over it doesn't produce the injected behavior).

## 11. Intended build order

1. Structured logging + request-ID middleware; the `LLMClient`-wrapping decorator for latency + `usage`.
2. Cost computation from `usage`; per-request + rolling logs.
3. The output-grounding guard (reuse Phase 6) wired into `/chat` and `/analyze`.
4. Prompt hardening: instruction hierarchy + delimiting untrusted content; the injection regression set.
5. Loader provenance/sanitization + the poisoned-document test.
6. (Optional) a tracing UI (§12); the ops note.

## 12. Open decisions for this phase

- **Observability tool.** Recommend **structured-logging-first** ($0, local, teaches the fundamentals:
  capture `usage`, time the stages, compute cost), then *optionally* add a tracing UI. Candidates to
  evaluate at build (verify current free tiers — this space moves fast): **Langfuse** (open-source,
  self-hostable, LLM-native), **Pydantic Logfire** (natural fit for a FastAPI/Pydantic stack, free
  tier), **OpenTelemetry + a free backend**, **Arize Phoenix** (local). Weigh $0/local vs. a nicer
  dashboard; lean local given the budget.
- **How hard to fail on a grounding-guard miss** — block the response, or serve it with a warning? Tune
  once real failure rates are visible.
- **Cost-rate source** — hardcode current per-token rates vs. fetch; rates churn, so isolate them in one
  config spot.

## 13. What this hands forward

- **To Phase 8 (hybrid retrieval):** traces + the cost/latency baseline make the retrieval change
  measurable in ops terms, not just eval scores.
- **To Phase 9 (the agent) — the load-bearing handoff:** the corpus-poisoning defense and the human
  gate are exactly what make it *safe* for an agent to auto-write to `corpus/`. Phase 9 should not ship
  without Phase 7's loader defenses in place.
- **To Phase 10 (MCP):** exposing tools over MCP widens the injection surface; the instruction-hierarchy
  and grounding-guard patterns carry forward.
