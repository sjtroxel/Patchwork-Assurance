# Phase 10 — MCP Server (the capstone)

*Phase plan (intended design), written 2026-06-17. The final phase (ROADMAP §6). Exposes Patchwork's
capabilities — scope check, memo, retrieval, metadata query — as a **Model Context Protocol (MCP)**
server, callable from Claude Desktop, Cursor, Claude Code, and any MCP client. It's a thin wrapper:
another consumer of the `core/` keystone, alongside the FastAPI API and the eval harness. MCP SDK
specifics churn — verify the current Python MCP SDK API at build (ROADMAP standing rule). The as-built
companion `phase-10-mcp-server-IMPLEMENTATION.md` is written when the phase begins.*

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
