# Phase 10 — MCP Server (the capstone)

*Phase plan (intended design), written 2026-06-17. The final phase (ROADMAP §6). Exposes Patchwork's
capabilities — scope check, memo, retrieval, metadata query — as a **Model Context Protocol (MCP)**
server, callable from Claude Desktop, Cursor, Claude Code, and any MCP client. It's a thin wrapper:
another consumer of the `core/` keystone, alongside the FastAPI API and the eval harness. MCP SDK
specifics churn — verify the current Python MCP SDK API at build (ROADMAP standing rule). The as-built
companion `phase-10-mcp-server-IMPLEMENTATION.md` is written when the phase begins.*

---

## 0. Catch-up before MCP — close the deferred `[-]` items + launch the public domain

*Added 2026-06-28. The Anthropic API key is now funded (~$20, up from $0.31 — the dollar that blocked
every paid run; the OpenRouter free-model detour didn't produce trustworthy memos). Before MCP we spend a
few of those dollars **once** to convert the willfully-deferred `[-]` measurement items into `[x]`, and we
put the public app under a real domain. The point isn't bookkeeping: when strangers generate compliance
memos next week, **the groundedness number is the evidence that those memos are trustworthy.** This
section is the plan; the as-built steps land in `phase-10-mcp-server-IMPLEMENTATION.md` tomorrow on fresh
quota. Standing rule: **token-spending commands are sjtroxel's to run**, like git.*

**Update 2026-06-29 — this §0 is now a parallel "ledger closure" track, decoupled from "strictly before
MCP."** Per sjtroxel's direction, the funded-run catch-up runs as **one paid validation per morning**
(ROADMAP §6 "funded-run ledger") while the roadmap build work proceeds alongside — and the **Phase 10 MCP
build (and its IMPLEMENTATION doc) is deliberately NOT started** until the still-to-do list is organized
and the Phase 11/12 scope docs are written. Done so far: **§0.3 Phase 6 ✅**, **§0.7 production smoke
test ✅**, **§0.8 custom domain ✅** (all 2026-06-29). Remaining paid runs: **Tue 6/30 = §0.4 Phase
7-live · Wed 7/1 = §0.5 Phase 8-live + the free N=7 re-sweep · Thu 7/2 = §0.11 Phase 9 first live PR**
(no longer "optional" — it's the launch headline; it needs the CO/CT privacy statute added first).

**Do these roughly in order — safety and the free win first, then the paid runs, then the domain.**

### 0.1 Pre-flight: spending safety (do this FIRST, before any paid command)
The $0.32 accidental-spend incident (`docs/SPENDING_SAFETY.md`, [[project-spending-incident-and-guardrail-2026-06-23]])
is exactly the failure mode a funded key makes more expensive. Before any `--judge`/`-m live` run:
- [ ] Set a **provider-side spend limit** on the Anthropic key (console hard cap), so neither an eval run
      nor a public-user surge can drain the whole balance.
- [ ] Re-confirm `eval/safety.py:confirm_spend` still gates every paid path (hard cap + typed confirm +
      refuse-if-unattended). It is the in-code chokepoint; the provider cap is the backstop.
- [ ] Note the **shared-wallet** reality: this one $20 funds both the one-time eval runs **and** every
      production memo real users generate (§0.9). Budget the eval runs against that.

### 0.2 Re-verify model IDs + pricing (standing rule, costs nothing)
- [ ] Re-verify the current model IDs + per-token pricing via the `claude-api` skill before spending
      (they churn): chat = Haiku, memo = Sonnet, judge = a *different/stronger* model (Opus) so the judge
      ≠ the judged. Pin them in the IMPLEMENTATION doc.

### 0.3 Phase 6 — the one judged run (closes the two `[-]` items + the model decision)
**✅ DONE 2026-06-29 ($4.57).** Groundedness 86.5%, citations-resolve 99.0%, coverage 78.4% (after fixing
the metric), models settled Sonnet+Opus. Both `[-]` flipped in `phase-6-evals.md` §2 (ticket RESOLVED);
results in `-IMPLEMENTATION.md` §10; session detail in [[project-judged-eval-run-2026-06-29]].
The single bounded ticket from `phase-6-evals.md` §2. **The confidence metric for the whole product.**
- [ ] Run `make eval-judge` (= `python -m eval.run --judge`, `LLM_PROVIDER=anthropic`) on the **full**
      gold set, behind the spend gate. Estimated **$1–3** one-time (Sonnet memo + Opus judge ≈ $1.65;
      Haiku+Sonnet ≈ $0.80 — confirm against §0.2 pricing).
- [ ] Produce the two owed numbers, aggregated over the gold set: **groundedness** (% of memo obligations
      fully supported by their cited statute text) and **coverage** (% of expected obligations surfaced).
      Citation-exists scores from the same run.
- [ ] **Resolve the Haiku-vs-Sonnet memo-model decision** from the measured groundedness gap (plan §8).
- [ ] **Read a handful of the generated memos by hand** — the number is necessary but not sufficient for
      "I'd let a stranger rely on this." This is the not-legal-advice boundary in practice.
- [ ] Record the numbers + measured cost back into `phase-6-evals-IMPLEMENTATION.md`, write the short
      results write-up, and flip both `[-]` → `[x]` in `phase-6-evals.md` (and the ROADMAP §6 row).

### 0.4 Phase 7 — live observability + injection (rides the same funded window)
From `phase-7-observability-security-IMPLEMENTATION.md` "deferred to a live run":
- [ ] First real **per-request cost numbers** — the "pennies per memo" claim, measured (not estimated),
      from `core/obs.py`/`core/pricing.py` capture on a live Anthropic call.
- [ ] **Live injection-resistance tests**: `pytest -m live` (deselected by default; spends tokens).
- [ ] The **ContextVar → threadpool `request_id` propagation** check on the live box (unit tests are
      same-thread, so this can only be confirmed live).
- [ ] Flip the Phase 7 deferred notes accordingly.

### 0.5 Phase 8 — judged retrieval numbers AND the free N=7 re-sweep (a real new finding may hide here)
Two parts — one paid, one free and arguably more important now:
- [ ] **Paid:** the text→SQL + agentic-`routed` *eval numbers* and the `live`-marked "does the model route
      well / write valid SQL" checks (`LLM_PROVIDER=anthropic`).
- [ ] **Free, do this regardless of budget:** re-run the deterministic sweep (`make eval --sweep`,
      `make sweep-knobs`) **now that the corpus is 7 laws, not 2.** The Phase 8 verdict ("semantic +
      metadata filter is enough; hybrid/routed/text→SQL tie or lose") was *explicitly an N=2 artifact*.
      At N=7 the fancier rungs may finally earn their keep — and if they do, the **default retrieval mode
      should change** (one config line). This costs nothing and could be the most interesting result of
      the whole catch-up. Re-confirm `bge-small`, `k=8`, chunk size at the new scale too.

### 0.6 Phase 4.6 — running-app QA that never closed
The spine still reads "**BUILT 2026-06-20 (96 tests; pending running-app QA)**." Tests pass; the app-level
walkthrough was never recorded.
- [ ] Exercise the **headline case in the running app** (not just tests): an out-of-state business with
      CO/CT employees/consumers/residents → correct nexus, roles, shadow-AI discovery, verdict-first memo
      with real deadlines. Confirm and close the QA note.

### 0.7 End-to-end production smoke test (the funded key, the deployed path)
**✅ DONE (memo) 2026-06-29.** The maximal Missouri property-mgmt memo (6 nexus states, employment +
housing) generated end-to-end through the live `app.patchworkassurance.com` → `api.` path in ~1 min, on
the funded key. CA two-regime split + per-domain scoping held. *Still worth a quick check:* one real
**chat** round-trip in production (the memo path is the one verified).
- [ ] One real memo + one real chat through the **deployed Railway** path on the funded key — the first
      genuine paid generation in production. Confirm streaming, the rate limit, and the chrome all behave.

### 0.8 Custom domain + the one-umbrella wiring
**✅ DONE 2026-06-29.** `patchworkassurance.com` (Cloudflare Registrar, $10.46/yr). apex+`www` → Vercel
landing, `app.` → Railway Streamlit, `api.` → Railway FastAPI (`/docs` exposed). All grey-cloud, HTTPS
verified, `API_BASE_URL`/CORS/README/landing-button updated, GitHub homepage flipped. Full wiring in
[[project-custom-domain-live-2026-06-29]].
The Phase 5 "custom-domain umbrella" was deferred to the post-v1 backlog; do it now (see
[[feedback-deploy-hosting-preferences]]: landing → free static host, UI + API → Railway always-on, no
cold-start).
- [ ] Register the domain (patchworkassurance.com or chosen name).
- [ ] Point the **landing page**, the **Streamlit UI**, and the **FastAPI API** under one domain (e.g.
      apex/`www` → landing, `app.` → Streamlit, `api.` → FastAPI) via Railway custom-domain + DNS.
- [ ] Update every **hardcoded URL**: landing-page links, README, the `ui/` chrome/footer, OpenGraph/meta
      tags, any `API_BASE`/CORS origin config. **Re-check CORS** — Phase 5 found it unneeded because the UI
      calls the API server-side; confirm that still holds across the new subdomains.
- [ ] Verify HTTPS/cert on every host before announcing.

### 0.9 Production cost-control before the public launch (new — the funded key changes the threat model)
Public users generating Sonnet memos spend real money against the same $20. Before announcing:
- [ ] Confirm the **memo rate limit** (~2 Sonnet memos / IP / day) is actually wired and enforced, and
      that **chat = Haiku** (cheap) as designed.
- [ ] Add a **global daily ceiling** or alert so a burst/abuse can't silently drain the balance (the
      provider cap from §0.1 is the hard backstop; this is the early-warning).

### 0.10 Surface-accuracy pass — 7 laws, everywhere (cheap, do before announcing)
Per [[feedback-proactive-jurisdiction-presentation-updates]] the §7-B hand-updates must be consistent.
- [ ] Verify the **README, landing page, UI copy, and the corpus list** all say **seven** jurisdictions
      (CO, CT, IL, CA×2, NYC, NJ) — no stale "CO/CT only" or "five laws" copy survives.

### 0.11 Phase 9 — the agent's first live PR (optional; can trail the launch)
- [ ] *Optional, lower priority for launch:* register an NJ-style `SourceEntry` and let the monitoring
      agent draft its **first live end-to-end PR**, converting Phase 9's one remaining deferred item to a
      demonstrated live run. Reasonable to defer until after MCP — it doesn't gate the public launch.

### Exit criteria for §0 (what "caught up" means)
Phases 6, 7, 8 have **zero `[-]` items left** (numbers measured, decisions resolved, write-ups recorded);
the app is live under its own domain with HTTPS and cost-control; the memo quality is backed by a real
groundedness number **and** a human read. Only then start the MCP build (§1+). MCP is intentionally last:
it exposes a `core/` that is now measured, trustworthy, and properly hosted.

---

## 1. What Phase 10 is

Making the engine reusable beyond its own UI.

Until now Patchwork's logic is reachable two ways: the Streamlit UI (via the API) and the eval harness.
Phase 10 adds a third door — an **MCP server** — so the same `core/` capabilities become **tools a model
can call from inside Claude Desktop, Cursor, or Claude Code.** A user could ask their assistant
"does Connecticut's AI law cover my hiring tool?" and it calls Patchwork's `check_scope` tool directly,
without leaving the chat.

This is the capstone because it's where the **keystone architecture pays off completely**: `core/` now
has multiple independent consumers — UI, evals, and MCP — all running the same logic with zero
duplication. The whole "thin shells over one core" design (ROADMAP §3) exists to make this phase a small
wrapper instead of a rewrite.

**Primary learning (ROADMAP §6):** MCP, and tool + server design.

---

## 2. Definition of done

- [ ] An **MCP server** (a `mcp/` package) exposing Patchwork's read-only capabilities as **tools**:
      `check_scope`, `generate_memo`, `search_corpus`, `query_metadata` (and a small
      `list_jurisdictions`).
- [ ] The server **imports `core/`** and wraps the existing functions — no business logic re-implemented
      (the keystone rule).
- [ ] It runs over a standard transport and **connects from a real MCP client** (Claude Desktop / Cursor
      / Claude Code) — a manual end-to-end call works.
- [ ] Tool outputs carry the **not-legal-advice disclaimer** (it rides in the memo payload already;
      ensure every tool surface includes it).
- [ ] The server is **read-only** — no corpus-write / ingestion tools exposed (§9).
- [ ] Tests cover the tool wrappers (input/output mapping) with `core` stubbed where needed.
- [ ] A short "connect it to your client" note in the README.

Done = Patchwork's engine is callable as MCP tools from a real client, read-only and disclaimed.

---

## 3. Explicitly NOT in Phase 10

- **No new product logic.** Every tool wraps an existing `core/` function. If MCP needs a capability
  `core/` doesn't have, that's a `core/` change, not MCP glue.
- **No write/ingestion tools over MCP** (§9). The Phase 9 monitoring/ingestion pipeline and its human
  gate stay internal — exposing corpus-write tools to arbitrary clients is the wrong risk to take.
- **No auth/multi-tenant server.** Local-first MCP (stdio) for v1; a hardened remote server is a later
  option, not this phase.
- **No abandoning the existing surfaces.** MCP is an *additional* door, not a replacement for the UI or
  API.

---

## 4. What MCP is (the learning)

The **Model Context Protocol** is an open standard (Anthropic-originated, now broadly adopted) for
connecting LLM clients to external capabilities. An MCP **server** exposes three kinds of thing:

- **Tools** — callable functions the model can invoke (our `check_scope`, `generate_memo`, …).
- **Resources** — readable data the client can pull in (optionally, our statute texts — §7).
- **Prompts** — reusable prompt templates (not needed for v1).

A **client** (Claude Desktop, Cursor, Claude Code, …) connects to the server; the model can then call
its tools as part of a conversation. So MCP is the standard that lets *any* compatible assistant use
Patchwork's engine — the "tool + server design" skill, learned by shipping a real one.

## 5. The tools to expose

All read-only, and already shaped as tools by Phases 8–9 (Phase 8 §15, Phase 9 §15):

| Tool | Wraps | Why it's a good MCP tool |
|---|---|---|
| `check_scope(situation)` | the deterministic scope screen (Phase 2 §6) | fast, deterministic, exact — the ideal first tool |
| `generate_memo(situation)` | `core.generate_memo` → `ComplianceMemo` | the demoable headline, as structured output |
| `search_corpus(query, filters)` | semantic retrieval (Seam 2 / Phase 8) | grounded passage lookup with citations |
| `query_metadata(question)` | text→SQL over the metadata table (Phase 8) | factual questions (dates, cure periods, scope) |
| `list_jurisdictions()` | corpus metadata | tells a client what's covered |

Tool schemas are Pydantic-derived (the same `Situation` / `ComplianceMemo` models — SPEC §8), so the MCP
tool contracts reuse the existing shapes; no third definition to drift.

## 6. The MCP server as the third consumer of `core/`

The satisfying structural conclusion:

```
                 ┌── api/   (FastAPI → Streamlit UI)
   core/  ◄──────┼── eval/  (the scorecard harness)
  (keystone)     └── mcp/   (this phase — MCP tools)
```

The MCP server is a **sibling to `api/`** — it imports `core/`, wraps `generate_memo` / `check_scope` /
`retrieve` / `query_metadata` as MCP tools, and adds nothing else. This is the keystone (ROADMAP §3, §4)
delivering exactly what it promised: one body of logic, many thin faces, no duplication. When this phase
is a 100-line wrapper instead of a reimplementation, the whole architecture is vindicated.

## 7. Resources (optional)

Beyond tools, the server can expose the **corpus statutes as MCP resources** — a readable resource per
law (cleaned text + metadata), so a client can pull the actual statutory text into context. Nice for
transparency ("show me the source"), low cost. Decide at build (§13); tools are the required surface,
resources are a bonus.

## 8. How to build (verify the SDK at build)

- Use the official **Python MCP SDK** (the `mcp` package / its `FastMCP` server helper) — decorator-based
  tool registration is the idiomatic pattern (`@server.tool()` wrapping a `core/` call). **Verify the
  current SDK API at build** — MCP and its SDK move fast, so confirm the exact decorators/transport
  names rather than trusting this doc's shape.
- **Transport: stdio first** — the standard local transport that Claude Desktop / Cursor / Claude Code
  use to launch and talk to a local MCP server. An HTTP/SSE transport for a *remote* server is an
  optional later add (§13).
- The server process constructs the `core/` dependencies once (the retriever, an `LLMClient`) — same
  lifespan/DI thinking as the FastAPI app (Phase 3 §7), just in an MCP server instead of a web app.

## 9. Security

- **Read-only surface.** Expose scope/memo/retrieval/metadata only. **No ingestion/write tools** — those
  stay behind the Phase 9 human gate; an MCP client must never be able to mutate the corpus.
- **The disclaimer rides in every tool output** (the memo carries it; add it to the others) — a client
  consuming `generate_memo` must receive the not-legal-advice framing (ROADMAP §5, §9;
  `.claude/rules/legal-content.md`).
- **Phase 7 hardening applies** — the grounding guard and prompt-injection defenses protect tools the
  same way they protect the API; treat tool inputs as untrusted.
- Local stdio server = no network exposure for v1; if a remote HTTP transport is added later, it needs
  the auth/rate-limit story this phase deliberately skips.

## 10. Config and dependencies added this phase

**Config additions:** which tools to enable; transport selection (`stdio` default); reuse of the
existing model/retrieval config.

**Dependencies:** the **Python MCP SDK** (`mcp`) — the one real addition. Pin the version in
IMPLEMENTATION (this SDK churns).

## 11. Testing

- **Tool-wrapper unit tests:** each MCP tool maps its inputs to the right `core/` call and returns the
  expected shape (with `core`/LLM stubbed where needed) — the wrappers are thin, so the tests are too.
- **Schema tests:** the tool schemas serialize from the shared Pydantic models correctly.
- **Manual end-to-end:** register the server in a real client (Claude Desktop / Cursor / Claude Code) and
  confirm a `check_scope` / `generate_memo` call round-trips with the disclaimer present.
- **Security:** confirm no write tool is exposed; confirm tool inputs route through the Phase 7 defenses.

## 12. Intended build order

1. The `mcp/` package + the MCP SDK; a single trivial tool (`list_jurisdictions`) over stdio; connect
   from a real client to prove the transport.
2. `check_scope` (deterministic, no LLM) — the clean first real tool; unit-test the wrapper.
3. `generate_memo`, `search_corpus`, `query_metadata` wrappers; ensure the disclaimer rides in outputs.
4. (Optional) corpus statutes as MCP resources (§7).
5. Confirm read-only (no write tools); wire Phase 7 defenses on inputs.
6. The "connect it to your client" README note; final end-to-end demo.

## 13. Open decisions for this phase

- **Transport: stdio only vs also HTTP/SSE.** Recommend **stdio for v1** (local clients, no network/auth
  surface); add a remote HTTP transport only if a hosted use case appears.
- **Resources or tools-only** (§7) — tools are required; statute resources are a low-cost bonus, decide
  by appetite.
- **Which tools to expose** — start with the five in §5; `generate_memo` is the headline, `check_scope`
  the cheapest/cleanest.
- **MCP SDK version/API** — verify current at build; this is the churniest dependency in the project.

## 14. What this means — the architecture, complete

- **The keystone is fully realized.** `core/` now serves the UI (via the API), the eval harness, and MCP
  clients — three independent consumers, one body of logic, zero duplication. Every "thin shell over
  `core/`" decision back to Phase 0 was for this moment, and it makes the capstone a wrapper.
- **The engine is portable.** Patchwork stops being "an app at a URL" and becomes "a capability your
  assistant can call" — the strongest framing of the AI-native thesis (ROADMAP §1).
- **The portfolio story is complete:** a grounded, evaluated, hardened, self-updating legal-compliance
  engine, exposed both as a web app and as MCP tools, built on a clean Python core. That is the full arc
  the roadmap set out to earn (ROADMAP §1, §6) — and the end of the planned phase spine. From here, it's
  building.
