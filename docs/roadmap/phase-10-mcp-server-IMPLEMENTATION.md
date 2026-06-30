# Phase 10 — MCP Server — IMPLEMENTATION

*As-built guide, written 2026-06-29 at phase start (companion to `phase-10-mcp-server.md`). Grounded in
the **actual current codebase** — every wrapped function signature below was read from `src/` on
2026-06-29, so the code skeletons are copy-accurate. This phase is a **thin wrapper**: the MCP server
imports `core/` and exposes existing functions as MCP tools; it re-implements **no** business logic
(the keystone rule, ROADMAP §4). The §0 catch-up (paid runs + domain) in the scope doc is a **separate
parallel track** and is NOT a prerequisite for this build.*

> **VERIFY-AT-BUILD (do this first, standing rule — the SDK churns):**
> 1. `pip show mcp` after install; **pin the exact version** in `pyproject.toml` and record it in §12.
> 2. Confirm the import path `from mcp.server.fastmcp import FastMCP` and the `@mcp.tool()` / `mcp.run(transport="stdio")`
>    API are still current (official SDK: github.com/modelcontextprotocol/python-sdk). If the API moved,
>    adapt the skeletons in §4 — the *wrapping* logic stays identical, only the decorator/run shape changes.
> 3. Re-confirm model IDs via the `claude-api` skill: as of now `memo_model=claude-sonnet-4-6`,
>    `chat_model=claude-haiku-4-5`. The server reuses `settings`, so it inherits whatever is configured —
>    no new model IDs to hardcode.

---

## 0. What you're wrapping (the core entry points, confirmed 2026-06-29)

All of these already exist; the MCP tools call them unchanged. Mirror how `api/main.py` uses them.

| Core function | Module | Signature (real) | LLM? |
|---|---|---|---|
| `applicable_laws` | `core.scope` | `(situation: Situation, laws: list[LawMetadata]) -> list[ScopeResult]` | No (deterministic) |
| `generate_memo` | `core.memo` | `(situation, scope, retriever, llm, laws) -> ComplianceMemo` | **Yes (Sonnet)** |
| `Retriever.query` | `core.retrieval` | `(query: str, filters: RetrievalFilters \| None = None, k: int = 5, mode: str = "filtered") -> list[RetrievedChunk]` | No (local embed) |
| `query_metadata` | `core.metadata_query` | `(question: str, conn: sqlite3.Connection, llm, *, mode="intent") -> list[dict]` | **Yes** |
| `build_metadata_db` | `core.metadata_query` | `(laws: list[LawMetadata]) -> sqlite3.Connection` | No |
| `corpus_vocab` | `core.meta` | `(laws: list[LawMetadata]) -> CorpusVocab` | No |

Supporting shapes (already defined — import, don't redefine): `Situation`, `ScopeResult`,
`ComplianceMemo`, `RetrievalFilters`, `RetrievedChunk`, `CorpusVocab` (all in `core.contracts` /
`core.retrieval`); `DISCLAIMER` in `core.prompts`.

**`RetrievalFilters`** fields: `jurisdiction`, `scope_domain`, `law_id` (all `str | None`).
**`RetrievedChunk`** fields: `text`, `citation`, `section_number`, `section_heading`, `jurisdiction`, `law_id`.

---

## 1. Dependency + Makefile

- Add the SDK to `pyproject.toml`. The Anthropic-originated official package is **`mcp`** (ships
  `mcp.server.fastmcp.FastMCP`). Pin the version you actually install (VERIFY-AT-BUILD #1):
  ```toml
  # [project] dependencies
  "mcp>=X.Y,<Z",   # pin the real installed version; record it in §12
  ```
  Then `pip install -e ".[dev]"`.
- Add a Makefile target:
  ```make
  mcp:  ## run the MCP server over stdio
  	python -m patchwork_assurance.mcp.server
  ```

## 2. Package layout

```
src/patchwork_assurance/mcp/
  __init__.py
  server.py        # FastMCP instance, dep construction, the 5 tools, __main__ entry
```
`mcp/` is a **sibling of `api/`** — it imports `core/`, nothing else from the app. (`core` still imports
inward only; do not import `api/` or `ui/` here.)

## 3. Construct the core deps once (mirror `api/main.py:lifespan`)

The server builds the same objects the FastAPI lifespan does, once at startup. Copy the lifespan body
(`api/main.py` lines 33–57) — do not invent a new construction path.

```python
# src/patchwork_assurance/mcp/server.py
from dataclasses import dataclass
from pathlib import Path

from patchwork_assurance.config import settings
from patchwork_assurance.core.contracts import Situation
from patchwork_assurance.core.corpus.loader import load_corpus
from patchwork_assurance.core.embeddings import FastEmbedEmbedder
from patchwork_assurance.core.lexical import build_lexical_index
from patchwork_assurance.core.llm import build_llm
from patchwork_assurance.core.memo import generate_memo as core_generate_memo
from patchwork_assurance.core.meta import corpus_vocab
from patchwork_assurance.core.metadata_query import build_metadata_db, query_metadata as core_query_metadata
from patchwork_assurance.core.prompts import DISCLAIMER
from patchwork_assurance.core.retrieval import RetrievalFilters, Retriever
from patchwork_assurance.core.scope import applicable_laws, load_law_metadata
from patchwork_assurance.core.vectorstore import ChromaVectorStore


@dataclass
class Deps:
    retriever: Retriever
    laws: list
    memo_llm: object
    meta_conn: object  # sqlite3.Connection


def build_deps() -> Deps:
    embedder = FastEmbedEmbedder()
    store = ChromaVectorStore(settings.chroma_path, embedder.model_name)
    if store.count() == 0:  # fresh checkout: build the index from the committed corpus (idempotent)
        load_corpus(Path(settings.corpus_path), store, embedder)
    lexical = build_lexical_index(Path(settings.corpus_path)) if settings.enable_lexical else None
    laws = load_law_metadata(Path(settings.corpus_path))
    return Deps(
        retriever=Retriever(store, embedder, lexical),
        laws=laws,
        memo_llm=build_llm(settings, settings.memo_model),
        meta_conn=build_metadata_db(laws),
    )


_deps = build_deps()  # built once at import; tools close over it
```

## 4. The five tools (read-only)

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Patchwork Assurance")  # name shown to the client


@mcp.tool()
def list_jurisdictions() -> dict:
    """List the jurisdictions, decision domains, and roles the corpus covers (free, deterministic)."""
    vocab = corpus_vocab(_deps.laws)
    return {**vocab.model_dump(), "disclaimer": DISCLAIMER}


@mcp.tool()
def check_scope(situation: Situation) -> dict:
    """Deterministic scope screen: which corpus laws apply to this situation (free, no LLM)."""
    results = applicable_laws(situation, _deps.laws)
    return {"results": [r.model_dump() for r in results], "disclaimer": DISCLAIMER}


@mcp.tool()
def search_corpus(
    query: str,
    jurisdiction: str | None = None,
    scope_domain: str | None = None,
    law_id: str | None = None,
    k: int = 8,
) -> dict:
    """Grounded passage lookup over the statute corpus, with citations (free; local embeddings)."""
    filters = RetrievalFilters(jurisdiction=jurisdiction, scope_domain=scope_domain, law_id=law_id)
    chunks = _deps.retriever.query(query, filters, k=k, mode=settings.retrieval_mode)
    return {"chunks": [c.model_dump() for c in chunks], "disclaimer": DISCLAIMER}


@mcp.tool()
def generate_memo(situation: Situation) -> dict:
    """Full educational compliance memo (COST-BEARING — Sonnet). Needs LLM_PROVIDER=anthropic + a key."""
    scope = applicable_laws(situation, _deps.laws)
    memo = core_generate_memo(situation, scope, _deps.retriever, _deps.memo_llm, _deps.laws)
    return memo.model_dump()  # ComplianceMemo already carries .disclaimer


@mcp.tool()
def query_metadata(question: str) -> dict:
    """Factual metadata questions (effective dates, cure periods, scope) over the law-metadata table
    (COST-BEARING — one LLM call; fails closed to an empty list)."""
    rows = core_query_metadata(question, _deps.meta_conn, _deps.memo_llm, mode="intent")
    return {"rows": rows, "disclaimer": DISCLAIMER}


if __name__ == "__main__":
    mcp.run(transport="stdio")
```

Notes:
- **FastMCP derives each tool's input schema from the type hints** — `Situation` (a Pydantic model)
  becomes the tool's argument schema automatically; the docstring becomes the tool description shown to
  the client. This is why the tool contracts reuse the existing Pydantic shapes (scope doc §5) — no third
  definition to drift.
- `k=8` matches `MEMO_RETRIEVAL_K`; `mode=settings.retrieval_mode` keeps the server on the same retrieval
  default as the app.

## 5. The disclaimer rule (every tool output)

Every tool returns the `DISCLAIMER` (the `generate_memo` memo already embeds `.disclaimer`; the other four
attach it explicitly, as above). A client consuming any tool must receive the not-legal-advice framing
(`.claude/rules/legal-content.md`, ROADMAP §5/§9). **Add a test that asserts this for every tool (§9).**

## 6. Read-only + security

- **Only the five read tools above.** Do NOT expose any corpus-write/ingestion tool — the Phase 9
  pipeline and its human gate stay internal; an MCP client must never mutate the corpus (scope doc §9).
- Treat tool inputs as untrusted; the Phase 7 grounding guard already protects the wrapped `core/` paths.
- `stdio` transport = local only, no network surface for v1. (HTTP/SSE remote transport is a later option,
  out of scope here.)

## 7. Running it

- `make mcp` (or `python -m patchwork_assurance.mcp.server`).
- For the **cost-bearing** tools (`generate_memo`, `query_metadata`) the env needs
  `LLM_PROVIDER=anthropic` + `ANTHROPIC_API_KEY`. With `LLM_PROVIDER=stub` (default), the three free tools
  (`list_jurisdictions`, `check_scope`, `search_corpus`) work fully and the cost-bearing tools return stub
  output — fine for wiring/dev.

## 8. Connecting from a client (README note)

stdio servers are launched by the client. Example Claude Desktop config (`claude_desktop_config.json`) —
verify the exact key names against current client docs at build:

```json
{
  "mcpServers": {
    "patchwork-assurance": {
      "command": "python",
      "args": ["-m", "patchwork_assurance.mcp.server"],
      "env": { "LLM_PROVIDER": "anthropic", "ANTHROPIC_API_KEY": "sk-ant-..." }
    }
  }
}
```
Use the venv's Python (absolute path) if the client doesn't inherit the project environment. Cursor /
Claude Code use the same shape. Add a short "connect it to your client" section to the README.

## 9. Tests (`tests/test_mcp_server.py`)

The wrappers are thin, so the tests are too. Use the existing `StubLLM` (no spend) and the offline
fixtures the eval/api tests already use.

- **Tool-wrapper unit tests:** each tool maps inputs → the right `core/` call → expected shape. Build
  `Deps` with a `StubLLM` and a small test corpus (reuse the api/eval test fixtures).
- **Disclaimer test (the legal-boundary lock):** assert every tool's output contains the disclaimer
  (the four explicit + `generate_memo`'s `.disclaimer`).
- **Schema test:** the tools register and their input schemas serialize from the Pydantic models
  (e.g. `check_scope` exposes the `Situation` schema).
- **Read-only test:** assert the registered tool set is exactly the five read tools — no write tool.
- **Manual e2e (record in §12):** register the server in a real client and confirm `check_scope` +
  `generate_memo` round-trip with the disclaimer present.

## 10. Build order (the checklist Sonnet follows)

1. [x] Add + pin `mcp`; `make mcp` target; `mcp/` package skeleton.
2. [x] `build_deps()` (mirror lifespan); confirm it constructs against the committed corpus.
3. [x] `list_jurisdictions` (free, trivial) → connect from a real client to prove the stdio transport.
4. [x] `check_scope` (free, deterministic) + its wrapper test.
5. [x] `search_corpus` (free, local embed) + test.
6. [x] `generate_memo` (cost-bearing) — disclaimer rides in `.model_dump()`; test with `StubLLM`.
7. [x] `query_metadata` (cost-bearing) + test.
8. [x] Disclaimer test across all five; read-only test; schema tests.
9. [x] README "connect it to your client" note; manual e2e; record as-built notes in §12.
10. [x] `ruff check . && ruff format --check . && pytest` green.

## 11. Open decisions (carry from scope doc §13; resolve while building)

- **Transport:** stdio only for v1 (recommended) — HTTP/SSE remote is a later add.
- **Resources (statute texts as MCP resources):** optional bonus (scope doc §7); skip for the first pass,
  add if appetite remains.
- **`query_metadata` model:** reuses `memo_model` (Sonnet) above; a cheaper model is fine if cost matters
  (it's a small structured call) — decide at build.

## 12. As-built notes (filled in 2026-06-30)

- `mcp` version pinned: **`mcp>=1.28,<2`** (1.28.1 installed; verified `pip show mcp`)
- FastMCP API confirmed current: `from mcp.server.fastmcp import FastMCP` ✅ · `@mcp.tool()` returns
  the original function unchanged (direct test calls work) ✅ · `mcp.run(transport="stdio")` ✅ ·
  tool introspection via `mcp._tool_manager.list_tools()` (sync) for tests ✅
- Model IDs: inherited from `settings` — no new IDs hardcoded. At build: `memo_model=claude-sonnet-4-6`,
  `chat_model=claude-haiku-4-5`. `query_metadata` reuses `memo_llm` (Sonnet) per open-decision §11.
- Manual e2e client + result: **verified 2026-06-30 in Claude Code.** `claude mcp add patchwork-assurance --scope project` (`.mcp.json`); `list_jurisdictions` → all 6 jurisdictions + disclaimer; `check_scope(jurisdictions=[Colorado], decision_domains=[employment], roles=[deployer])` → CO SB 26-189 in scope, 6 others filtered on nexus. Deterministic gate confirmed working without an LLM (`LLM_PROVIDER=stub`).
- Deviations from plan:
  - `_deps` is **lazy** (`_deps: Deps | None = None` + `_get_deps()`) rather than module-level
    `build_deps()` — tools look up `_deps` via `_get_deps()` at call time. This keeps imports cheap and
    lets tests monkeypatch `server._deps` without triggering a corpus load. Functionally identical for
    production; the `__main__` block calls `_get_deps()` to warm up before `mcp.run()`.
  - Tests use two fixtures (`test_deps` / `meta_test_deps`) because `StubLLM.complete_structured` with
    `MetadataIntent` returns `model_construct()` (missing `field`), which crashes `lookup_intent`. The
    `meta_test_deps` fixture uses `StubLLM(structured=MetadataIntent(field="cure_period"))` instead.
