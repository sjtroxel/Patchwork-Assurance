# Phase 2 — IMPLEMENTATION (as-built runbook)

*The executable steps for Phase 2, prepared 2026-06-18 (Phases 0–1 complete: corpus indexed, 50 chunks,
both statutes re-OCR'd and integrity-verified). Companion to the design in
[`phase-2-core-logic.md`](phase-2-core-logic.md); contracts land in [`../SPEC_V1.md`](../SPEC_V1.md) §8.
Built on the Phase 1 `core/` (the `Embedder`, `VectorStore`, `LawMetadata`, and flattened chunk metadata).
This is the builder's first RAG + prompting + structured-output work — written to teach.*

> **High-confidence vs verify-at-build.** The deterministic scope screen (§6), the Pydantic contracts,
> the `StubLLM`, and the module wiring are stable Python — copy them. The **Anthropic SDK calls**
> (`messages.parse`, `messages.stream`) and **model IDs** churn; they were verified against the
> `claude-api` skill on **2026-06-18** (below), but re-confirm via `/claude-api` before trusting them at build.
>
> **The Sonnet-vs-Opus split for this phase.** Most of Phase 2 is ordinary, well-specified software
> engineering — retrieval plumbing, the LLM seam, the stub, orchestration, tests — squarely Sonnet's lane,
> executed against this runbook. **Two surfaces want Opus eyes / careful human review before they're
> trusted, for the same reason Phase 1's corpus did: a subtle error is a *legal* error, not a crash:**
> (1) the **deterministic scope screen** (§6) — the rules that decide which law applies and where
> `uncertain` is the honest answer; (2) the **system prompt + legal-content guardrails** (§9) — the
> permitted/prohibited-language boundary. Build everything else on Sonnet; pause on those two.

---

## 0. Verified-at-build facts (Anthropic API, via `claude-api` skill 2026-06-18)

- **Models / pricing** (the Phase 2 plan's choices, confirmed current):
  - Demo/generation path: **`claude-haiku-4-5`** — $1 / $5 per 1M (200K context, 64K max output). Supports
    structured outputs and streaming.
  - Quality-bump option (Phase 6, behind Seam 4): **`claude-sonnet-4-6`** — $3 / $15 per 1M.
  - Use the **bare** IDs exactly — no date suffix.
- **Structured output:** `client.messages.parse(model=..., max_tokens=..., messages=..., output_format=Schema)`
  returns a response whose **`.parsed_output`** is a validated Pydantic instance. Haiku 4.5 supports it.
  - **Schema limitation (design around it):** structured-output JSON Schema does **not** support numeric
    constraints (`minimum`/`maximum`), string-length constraints (`minLength`/`maxLength`), or recursive
    schemas; every object needs `additionalProperties: false`. The Python SDK strips unsupported
    constraints and validates them client-side, but **keep the memo Pydantic models free of `min_length`,
    `ge`, `le`, etc.** to avoid surprises.
- **Streaming:** `with client.messages.stream(model=..., max_tokens=..., messages=...) as s: for t in s.text_stream: ...`;
  `s.get_final_message()` for the full message. (No `thinking` param on Haiku — leave it off.)
- **Client/auth:** `anthropic.Anthropic()` reads `ANTHROPIC_API_KEY` from env. Never commit the key
  (already git-ignored). Default the dev/test path to the stub so nothing needs a key.
- **max_tokens defaults:** ~16000 for the (non-streaming) memo `parse` call; up to ~64000 for streamed chat.

---

## Step 1 — dependencies & config

Add to `pyproject.toml` `dependencies`:

```toml
    "anthropic",
```

Then `pip install -e ".[dev]" && pip freeze > requirements-lock.txt`.

Add to `config.py` `Settings` (defaults keep tests offline and free):

```python
    llm_provider: str = "stub"          # "stub" | "anthropic"
    generation_model: str = "claude-haiku-4-5"
    anthropic_api_key: str | None = None  # read from env ANTHROPIC_API_KEY; never commit
    top_k: int = 5
    max_tokens: int = 16000
```

> `pydantic-settings` maps `ANTHROPIC_API_KEY` → `anthropic_api_key` automatically (case-insensitive).
> Leave `llm_provider="stub"` as the default so `make test` and a fresh clone need no key.

---

## Step 2 — shared contracts (`core/contracts.py`)

One module for the cross-cutting Pydantic types so SPEC §8 mirrors one file. **No min/max/length
constraints** (structured-output limitation, §0). Stable — copy.

```python
from typing import Literal

from pydantic import BaseModel

from patchwork_assurance.core.corpus.metadata import RegulatedRole, ScopeDomain

InScope = Literal["yes", "no", "uncertain"]


# ---- retrieval ----
class RetrievedChunk(BaseModel):
    text: str
    citation: str
    section_number: str
    section_heading: str
    jurisdiction: str
    law_id: str
    score: float


# ---- scope input (the inspiration article's scope test, structured) ----
class Situation(BaseModel):
    """User-described facts. Drives the deterministic scope screen (§6)."""
    jurisdictions: list[str] = []          # nexus: states they operate in / employ / serve people in
    decision_domains: list[ScopeDomain] = []  # which decisions AI touches (employment, lending, ...)
    roles: list[RegulatedRole] = []        # developer / deployer
    uses_ai_in_decisions: bool = True
    notes: str = ""                        # free text, passed to the LLM for color (never to the screen)


# ---- scope output (deterministic) ----
class ScopeResult(BaseModel):
    law_id: str
    short_name: str
    jurisdiction: str
    in_scope: InScope
    reason: str                            # derived, human-readable


# ---- memo output ----
class MemoObligation(BaseModel):
    text: str
    citation: str


class LawFinding(BaseModel):
    law_id: str
    short_name: str
    in_scope: InScope
    why: str
    obligations: list[MemoObligation] = []
    effective_dates: list[str] = []


class DraftNotice(BaseModel):
    kind: str                              # e.g. "point-of-interaction", "pre-decision"
    jurisdiction: str
    text: str


class DeadlineItem(BaseModel):
    date: str
    what: str
    law: str


class ComplianceMemo(BaseModel):
    per_law: list[LawFinding]
    draft_notices: list[DraftNotice] = []
    deadline_checklist: list[DeadlineItem] = []
    disclaimer: str                        # the not-legal-advice line, always present


# ---- chat ----
class Msg(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatTurn(BaseModel):
    reply: str
    citations: list[str] = []
```

---

## Step 3 — the LLM seam (`core/llm.py`) — Seam 4

One Protocol, two implementations. **Verify the SDK calls (§0) at build.** `core/` imports only the
Protocol; only this file imports `anthropic`.

```python
from collections.abc import Iterator
from typing import Protocol, TypeVar

from pydantic import BaseModel

from patchwork_assurance.core.contracts import Msg

T = TypeVar("T", bound=BaseModel)


class LLMClient(Protocol):
    def complete(self, system: str, messages: list[Msg], max_tokens: int = 16000) -> str: ...
    def complete_structured(self, system: str, messages: list[Msg], schema: type[T]) -> T: ...
    def stream(self, system: str, messages: list[Msg], max_tokens: int = 16000) -> Iterator[str]: ...


class AnthropicLLM:
    """Wraps the official `anthropic` SDK. Verify messages.parse / messages.stream at build (§0)."""

    def __init__(self, model: str, api_key: str | None = None) -> None:
        import anthropic

        self._model = model
        self._client = anthropic.Anthropic(api_key=api_key)  # api_key=None → reads env

    def _dump(self, messages: list[Msg]) -> list[dict]:
        return [{"role": m.role, "content": m.content} for m in messages]

    def complete(self, system, messages, max_tokens=16000) -> str:
        resp = self._client.messages.create(
            model=self._model, max_tokens=max_tokens, system=system, messages=self._dump(messages)
        )
        return next((b.text for b in resp.content if b.type == "text"), "")

    def complete_structured(self, system, messages, schema):
        resp = self._client.messages.parse(
            model=self._model, max_tokens=16000, system=system,
            messages=self._dump(messages), output_format=schema,
        )
        return resp.parsed_output

    def stream(self, system, messages, max_tokens=16000):
        with self._client.messages.stream(
            model=self._model, max_tokens=max_tokens, system=system, messages=self._dump(messages)
        ) as s:
            yield from s.text_stream


class StubLLM:
    """Deterministic, offline, schema-valid output for tests/dev. The whole reason Seam 4 exists.
    Accepts canned values so a test can assert the pipeline shape without a network or key."""

    def __init__(self, text: str = "(stub)", structured: BaseModel | None = None) -> None:
        self._text = text
        self._structured = structured

    def complete(self, system, messages, max_tokens=16000) -> str:
        return self._text

    def complete_structured(self, system, messages, schema):
        # If a canned instance was supplied, return it; else build a minimal valid one.
        return self._structured if self._structured is not None else _minimal(schema)

    def stream(self, system, messages, max_tokens=16000):
        yield from self._text.split()


def _minimal(schema):
    """Best-effort minimal valid instance for a Pydantic model with all-defaulted/empty fields.
    For ComplianceMemo, tests should pass an explicit `structured=` instead."""
    return schema.model_construct()


def build_llm(settings) -> LLMClient:
    if settings.llm_provider == "anthropic":
        return AnthropicLLM(settings.generation_model, settings.anthropic_api_key)
    return StubLLM()
```

> The factory (`build_llm`) is the one place provider choice lives. The API layer (Phase 3) and the eval
> harness (Phase 6) both construct via it — same path, no parallel code.

---

## Step 4 — retrieval (`core/retrieval.py`) — Seam 2

Add the **query side**. First extend the Phase 1 `VectorStore` so the contract is explicit, then a
`Retriever` that owns the embedder + the mismatch guard.

**4a. Extend `core/vectorstore.py`** — add a `query` method to the Protocol and `ChromaVectorStore`:

```python
# in VectorStore(Protocol):
    def query(self, embedding, k, where) -> dict: ...

# in ChromaVectorStore:
    def query(self, embedding, k, where=None):
        return self._collection.query(
            query_embeddings=[embedding], n_results=k, where=where or None,
            include=["documents", "metadatas", "distances"],
        )
```

> Verify the `chromadb` `query`/`include` shape at build (it's version-sensitive like the Phase 1 calls).
> Chroma returns dict-of-lists keyed by query; index `[0]`. `where=None` means unfiltered.

**4b. `core/retrieval.py`:**

```python
from pydantic import BaseModel

from patchwork_assurance.core.contracts import RetrievedChunk


class RetrievalFilters(BaseModel):
    jurisdiction: str | None = None
    scope_domain: str | None = None        # e.g. "employment" -> matches scope_employment=True


def _where(filters: RetrievalFilters | None) -> dict | None:
    if not filters:
        return None
    clauses = []
    if filters.jurisdiction:
        clauses.append({"jurisdiction": filters.jurisdiction})
    if filters.scope_domain:
        clauses.append({f"scope_{filters.scope_domain}": True})
    if not clauses:
        return None
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}


class Retriever:
    def __init__(self, store, embedder) -> None:
        # The mismatch guard (rag.md rule 1 / SPEC §7): same model at ingest and query, or raise.
        stamped = store.embedding_model()
        if stamped and stamped != embedder.model_name:
            raise ValueError(
                f"embedding model mismatch: collection={stamped!r} query={embedder.model_name!r}"
            )
        self._store, self._embedder = store, embedder

    def retrieve(self, query: str, filters: RetrievalFilters | None = None, k: int = 5
                 ) -> list[RetrievedChunk]:
        emb = self._embedder.embed([query])[0]
        res = self._store.query(emb, k, _where(filters))
        out: list[RetrievedChunk] = []
        for doc, meta, dist in zip(
            res["documents"][0], res["metadatas"][0], res["distances"][0], strict=True
        ):
            out.append(RetrievedChunk(
                text=doc, citation=meta["citation"], section_number=meta["section_number"],
                section_heading=meta["section_heading"], jurisdiction=meta["jurisdiction"],
                law_id=meta["law_id"], score=1.0 - float(dist),  # cosine distance -> rough similarity
            ))
        return out
```

> **Filters are additive, never branched per-state** — two statutes and twenty hit this one path (Seam 2).
> Retrieval is generic; no `if colorado`.

---

## Step 5 — the deterministic scope screen (`core/scope.py`) — Seam 3 ★ Opus/human review

**This is the load-bearing legal logic. No LLM.** Which laws apply is *computed* from corpus metadata +
the `Situation`, and `uncertain` is first-class. Get the rules and especially the `uncertain` boundaries
reviewed carefully — this is where a subtle error becomes a wrong compliance answer.

```python
from pathlib import Path

import yaml

from patchwork_assurance.core.contracts import ScopeResult, Situation
from patchwork_assurance.core.corpus.metadata import LawMetadata


def load_law_metadata(corpus_path: Path) -> list[LawMetadata]:
    return [LawMetadata(**yaml.safe_load(f.read_text()))
            for f in sorted(corpus_path.glob("*.meta.yaml"))]


def applicable_laws(situation: Situation, laws: list[LawMetadata]) -> list[ScopeResult]:
    """Match the situation against each law's metadata — generic over N statutes (no `if colorado`).
    Returns one ScopeResult per law. `uncertain` is honest, not a cop-out."""
    results = []
    for law in laws:
        results.append(_screen_one(situation, law))
    return results


def _screen_one(situation: Situation, law: LawMetadata) -> ScopeResult:
    nexus = law.jurisdiction in situation.jurisdictions
    domain_overlap = set(situation.decision_domains) & set(law.scope_domains)
    role_overlap = set(situation.roles) & set(law.regulated_roles)

    if not situation.uses_ai_in_decisions:
        verdict, reason = "no", "No AI is used to make or influence the relevant decisions."
    elif not nexus:
        # No stated nexus to this jurisdiction. Honest 'uncertain' if they gave NO jurisdictions at all,
        # because 'doing business' thresholds are unlitigated/AG-rulemaking (ROADMAP §9).
        if not situation.jurisdictions:
            verdict, reason = "uncertain", (
                f"No jurisdictional nexus provided; whether {law.jurisdiction}'s 'doing business' "
                "threshold is met is fact-specific and unsettled."
            )
        else:
            verdict, reason = "no", f"No stated nexus to {law.jurisdiction}."
    elif domain_overlap and role_overlap:
        verdict, reason = "yes", (
            f"Operates in {law.jurisdiction}, acts as {'/'.join(sorted(role_overlap))}, and uses AI in "
            f"{'/'.join(sorted(domain_overlap))} decisions — facially within {law.short_name}."
        )
    elif domain_overlap or role_overlap:
        verdict, reason = "uncertain", (
            f"Some overlap with {law.short_name} (jurisdiction + "
            f"{'domain' if domain_overlap else 'role'}), but not all scope elements are clearly met."
        )
    else:
        verdict, reason = "no", (
            f"Nexus to {law.jurisdiction}, but the AI use doesn't touch a regulated domain or role under "
            f"{law.short_name}."
        )
    return ScopeResult(law_id=law.law_id, short_name=law.short_name,
                       jurisdiction=law.jurisdiction, in_scope=verdict, reason=reason)
```

> The LLM **never overrides** this verdict (§7). It renders the verdict into grounded prose and drafts
> notices. Keeping candidacy deterministic is the senior move and keeps the memo auditable.
>
> **Test this hardest (§12):** CO lending → CO yes / CT no; employment AI in both states → both yes; no
> nexus given → uncertain for both; nexus but unrelated domain → no. The table is the highest-value test
> surface in the app and needs no LLM.

---

## Step 6 — memo generation (`core/memo.py`) — Seam 3

One template, one schema, grounded output. Assemble `{situation, applicable_laws, retrieved_chunks}`,
instruct the model to ground every obligation in the provided chunks and cite them, return a validated
`ComplianceMemo` via `complete_structured`.

```python
from patchwork_assurance.core.contracts import ComplianceMemo, ScopeResult, Situation
from patchwork_assurance.core.prompts import MEMO_SYSTEM, render_memo_user
from patchwork_assurance.core.contracts import Msg


def generate_memo(situation: Situation, scope: list[ScopeResult], retriever, llm) -> ComplianceMemo:
    # Retrieve grounding for the laws that are in/maybe-in scope, filtered by jurisdiction.
    chunks = []
    for s in scope:
        if s.in_scope in ("yes", "uncertain"):
            from patchwork_assurance.core.retrieval import RetrievalFilters
            chunks += retriever.retrieve(
                query=_focus(situation), filters=RetrievalFilters(jurisdiction=s.jurisdiction), k=5
            )
    user = render_memo_user(situation, scope, chunks)
    return llm.complete_structured(MEMO_SYSTEM, [Msg(role="user", content=user)], ComplianceMemo)


def _focus(situation: Situation) -> str:
    return (f"obligations for {'/'.join(situation.roles) or 'a business'} using AI in "
            f"{'/'.join(situation.decision_domains) or 'consequential'} decisions")
```

> Haiku-class supports structured outputs, so the cheap path returns a typed memo by construction.
> Build the memo **first and most carefully** — it's the demoable surface.

---

## Step 7 — chat RAG (`core/chat.py`)

Thin once §3–5 exist. Stateless: caller passes full history (matches the stateless API).

```python
from collections.abc import Iterator

from patchwork_assurance.core.contracts import ChatTurn, Msg
from patchwork_assurance.core.prompts import CHAT_SYSTEM, render_grounding


def _ground(messages: list[Msg], retriever) -> tuple[str, list[str]]:
    last_user = next((m.content for m in reversed(messages) if m.role == "user"), "")
    chunks = retriever.retrieve(last_user, k=5)
    return render_grounding(chunks), [c.citation for c in chunks]


def chat(messages: list[Msg], retriever, llm) -> ChatTurn:
    grounding, citations = _ground(messages, retriever)
    reply = llm.complete(CHAT_SYSTEM + "\n\n" + grounding, messages)
    return ChatTurn(reply=reply, citations=citations)


def chat_stream(messages: list[Msg], retriever, llm) -> Iterator[str]:
    grounding, _ = _ground(messages, retriever)
    yield from llm.stream(CHAT_SYSTEM + "\n\n" + grounding, messages)
```

> **Shaped for SSE:** `chat_stream` exposes the token iterator Phase 3 wires to FastAPI; `chat` is the
> full-response helper. Phase 2 just produces both.

---

## Step 8 — prompts & the legal boundary (`core/prompts.py`) — §9 ★ Opus/human review

Where `.claude/rules/legal-content.md` becomes code. **Review this against the permitted/prohibited list
before trusting it.** The system prompt encodes: ground every claim in the provided statute chunks with
citations; never assert settled law on unlitigated questions; hold the auditor's "reasonable assurance"
framing; use permitted, avoid prohibited language; always carry the not-legal-advice disclaimer.

```python
DISCLAIMER = (
    "This is an educational analysis, not legal advice. The laws are new and unlitigated and subject to "
    "AG rulemaking. Consult a licensed attorney for a compliance decision."
)

MEMO_SYSTEM = f"""You produce a grounded, educational statutory-compliance summary — NOT legal advice, \
NOT a prediction of litigation outcomes (these statutes are unlitigated, so cite statute SECTIONS, never \
case law). Ground every obligation ONLY in the provided statute excerpts and cite the section. If the \
provided text does not support a claim, omit it. Use hedged, educational language ("the statute \
requires", "this appears to be in scope"); never say "you are compliant", "you must", "we certify/\
guarantee", or present unsettled interpretation as settled. Always set the disclaimer field to exactly: \
{DISCLAIMER}"""

CHAT_SYSTEM = f"""You are an educational assistant for US state AI-regulation law. Answer ONLY from the \
provided statute excerpts and cite sections. Decline or hedge on out-of-scope or unlitigated questions. \
Never give legal advice or assert settled law on unsettled questions. {DISCLAIMER}"""


def render_memo_user(situation, scope, chunks) -> str: ...   # situation + deterministic verdicts + excerpts
def render_grounding(chunks) -> str: ...                     # excerpts block with citations
```

> The disclaimer + the deterministic-scope hedging are **structural** — they survive into the
> `ComplianceMemo` schema and the chat posture, not "vibes". Keep the J.D. framed as a narrow edge.

---

## Step 9 — expose the surface (`core/__init__.py`)

```python
from patchwork_assurance.core.chat import chat, chat_stream
from patchwork_assurance.core.memo import generate_memo
from patchwork_assurance.core.retrieval import Retriever, RetrievalFilters
from patchwork_assurance.core.scope import applicable_laws, load_law_metadata

__all__ = ["chat", "chat_stream", "generate_memo", "Retriever", "RetrievalFilters",
           "applicable_laws", "load_law_metadata"]
```

> Done = `from patchwork_assurance.core import generate_memo, chat, applicable_laws` works and is tested.
> No web layer (Phase 3).

---

## Step 10 — tests (offline, no key; stub LLM)

- **`test_scope.py` (the crown jewel — exhaustive, no LLM):** a table of `Situation` → expected per-law
  `in_scope`, including every `uncertain` case. CO lending → CO yes / CT no; employment AI both → both
  yes; no nexus → uncertain; nexus + unrelated domain → no; `uses_ai_in_decisions=False` → all no.
- **`test_retrieval.py`** against the Phase 1 fixture corpus: filters scope correctly; the
  embedding-model-mismatch guard **raises**; a `_StubStore` returning canned Chroma-shaped dicts keeps it
  offline (no model download).
- **`test_memo.py` / `test_chat.py`** with `StubLLM(structured=<a valid ComplianceMemo>)`: assert the
  pipeline assembles `{situation, scope, chunks}`, calls the seam, returns a valid `ComplianceMemo` /
  `ChatTurn`, and that the disclaimer is always present. No network, runs in CI.
- **Live smoke tests** (real `claude-haiku-4-5`) behind a `@pytest.mark.live` marker + env flag — run
  manually, never in CI (keeps CI free/offline). One memo, one chat.

Wire the marker in `pyproject.toml` (`[tool.pytest.ini_options] markers = ["live: hits the real API"]`)
and default-deselect with `addopts = "-m 'not live'"`.

---

## Step 11 — SPEC §8

Replace the SPEC §8 "reserved" stub with the settled shapes: `Situation`, `RetrievedChunk`, `ScopeResult`,
`ComplianceMemo` (+ `LawFinding`/`MemoObligation`/`DraftNotice`/`DeadlineItem`), `Msg`, `ChatTurn`. Define
once there; reference, don't duplicate. Phase 3 serializes exactly these.

---

## Intended build order (mirrors plan §13)

1. Contracts (`core/contracts.py`) + `RetrievedChunk`/`Situation` — the vocabulary everything shares.
2. `core/vectorstore.py` `query()` + `core/retrieval.py`; test filters + the mismatch guard on the fixture.
3. `core/llm.py` Protocol + `StubLLM`; then `AnthropicLLM` (verify SDK calls).
4. **`core/scope.py`** + exhaustive `test_scope.py` — *before any LLM is involved*. ★ review.
5. `core/prompts.py` + `core/memo.py`; test orchestration on the stub; one live Haiku smoke. ★ review prompts.
6. `core/chat.py` (full-response then the streaming iterator) on the same retriever + seam.
7. `core/__init__.py` exports; SPEC §8; `make test` + `make lint` green; CI green.

---

## Definition of done (from plan §2)

- [ ] `Retriever.retrieve(query, filters, k)` on the Phase 1 store: embeds the query, asserts the model
      matches the collection tag (mismatch raises), similarity search with optional additive filters,
      returns typed `RetrievedChunk`s carrying citations.
- [ ] `LLMClient` Protocol with `AnthropicLLM` + `StubLLM`; nothing in `core/` imports `anthropic` directly.
- [ ] Deterministic `applicable_laws(situation, laws)` — no LLM, fully unit-tested, `uncertain` first-class.
- [ ] `generate_memo(...)` returns a validated `ComplianceMemo` grounded in retrieved text with citations,
      carrying the disclaimer.
- [ ] `chat(...)` multi-turn RAG over the same retriever + a streaming `chat_stream(...)` iterator.
- [ ] Tests pass with no network/key via the stub; live smoke tests gated behind a marker.
- [ ] `ComplianceMemo`/`Situation`/`RetrievedChunk`/chat shapes added to SPEC §8.
- [ ] `from patchwork_assurance.core import generate_memo, chat, applicable_laws` works; CI green.

---

## As-built notes (2026-06-18)

- **`anthropic` pinned at 0.111.0** (installed via `pip install -e ".[dev]"`).
- **Chroma `where` filter syntax:** equality filters require `{"field": {"$eq": value}}`, not bare
  `{"field": value}`. Updated in `core/retrieval.py` `_where()`.
- **SDK calls statically verified against the installed 0.111.0** (not just the skill): `messages.parse`
  accepts `output_format=` and returns a `.parsed_output` property; `messages.stream(...).text_stream`
  is a real instance attribute. **Caveat: the `AnthropicLLM` path has NOT been run end-to-end** — no
  API key has exercised it. The gated live smoke tests in `tests/test_live.py` (`@pytest.mark.live`,
  deselected by default, skip without `ANTHROPIC_API_KEY`) are the intended proof; run them before
  Phase 3 leans on the real model.
- **Retrieval `score`:** the Chroma collection is `space: l2` (squared L2), and fastembed BGE vectors
  are unit-normalized, so `score = 1 - distance/2` (cosine). Earlier `1 - distance` was metric-wrong
  (could go negative). See `_l2sq_to_cosine` in `core/retrieval.py`.
- **Citations are section-level, not law-wide.** `RetrievedChunk.pinpoint` composes a section cite
  (`Colorado § 6-1-1703` / `Connecticut Sec. 4`) generically; the render helpers feed it to the model
  and `chat()` returns deduped pinpoints. The law-wide `citation` is still carried for context.
- **Scope screen reworked to a 3-state model (human-reviewed 2026-06-18).** Each necessary element
  (jurisdiction / domain / role) is now `match | mismatch | blank`, so the screen distinguishes "you
  didn't tell me" (→ uncertain) from "you told me, and it's outside this law" (→ no). This removed the
  old false-reassurance bug (nexus-only with blank domain/role used to return a confident `no`; now
  `uncertain`). Strictness is a single `ScopePolicy` dial — `CAUTIOUS` (default), `LENIENT`, `STRICT` —
  so "too permissive / too strict" is a one-line change. Verdict semantics pinned in SPEC §8.2.
  Exemption/size-threshold modeling is still **not** present (the `LawMetadata` schema doesn't capture
  it); "yes" is therefore stated as "facially within", before exemptions. Deferred to a later phase.
- **53 tests passing (+2 live, deselected), lint clean.** No deviations from the intended build order.
- **SPEC §8 filled** with the settled shapes: `Situation`, `ScopeResult`, `RetrievedChunk`,
  `ComplianceMemo` (+ sub-types), `Msg`, `ChatTurn`. Phase 3 serializes exactly these.
- **`from patchwork_assurance.core import generate_memo, chat, applicable_laws` works.**
