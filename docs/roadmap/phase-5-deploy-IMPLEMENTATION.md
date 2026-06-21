# Phase 5 — IMPLEMENTATION (deploy + the model/rate-limit batch first)

*As-built runbook for Phase 5, written at phase start (2026-06-20), reflecting how Phases 0–4.6 landed.
Strategy/rationale lives in `phase-5-deploy.md` (read it first). Per the builder's call, Phase 5 **starts
with the generation batch** — the Anthropic API key, the two-model split, and the memo rate limit —
because that's what turns the app from the free stub into the real product; deploy follows. Fill the
as-built notes (§10) during the build. Cadence unchanged: Opus scaffolds; **sjtroxel runs all terminal +
git** (never Opus).*

---

## 0. Verified-at-build facts (confirm before relying on them)

- **Model IDs + pricing churn — re-verify at build** (the `claude-api` skill / `GET /v1/models`). As of
  the skill's 2026-06-04 table: **`claude-haiku-4-5`** ($1 / $5 per 1M in/out, 200K ctx) and
  **`claude-sonnet-4-6`** ($3 / $15 per 1M, 1M ctx). Do not hardcode from memory; pin in this doc once
  re-checked.
- **Generation is the `StubLLM` until `LLM_PROVIDER=anthropic` + `ANTHROPIC_API_KEY` are set.** Retrieval
  and the deterministic scope/deadlines/next-steps are already real; only the prose is stubbed.
- **Today the API builds ONE LLM** (`build_llm(settings)` → `app.state.llm`, used by both `/analyze` and
  `/chat`) on a single `settings.generation_model`. Phase 5 splits this into chat (Haiku) vs memo (Sonnet).
- **Railway** is the host (active Hobby sub); always-on, custom domains on Hobby. Re-confirm domain/cost
  at deploy (`phase-5-deploy.md` §13 open items — still unchecked there on purpose).
- **Statelessness is an invariant** (no DB, no saved history). The rate limiter must therefore be
  **in-memory** (counts, not user inputs; resets on restart) — see §2c.

## 1. Build order

1. **Generation batch (this doc's focus): API key → two-model config → memo rate limit** (§2).
2. Production embeddings decision (local vs OpenAI) + confirm index rebuild at startup (`phase-5-deploy.md` §9).
3. Deploy backend to Railway; set secrets; `/health` over HTTPS.
4. Deploy Streamlit UI to Railway (always-on); set `api_base_url`.
5. Set backend CORS to the live UI origin; verify the cross-origin call.
6. Deploy static landing (`site/`) to a free static host; point its CTA at the live UI.
7. (Optional) custom-domain umbrella: apex → landing, `app.` → UI.
8. Public README (`phase-5-deploy.md` §8); `.gitattributes` byte-ratio backstop (incl. `site/**` if needed).
9. End-to-end public smoke; final pass.

---

## 2. Step 1 — the generation batch (start here)

### 2a. Anthropic API key (guide the builder)
- Create a key at **console.anthropic.com → API Keys**; copy it once.
- Locally: `cp .env.example .env` (if not already), then set in `.env`:
  ```
  LLM_PROVIDER=anthropic
  ANTHROPIC_API_KEY=sk-ant-...
  ```
- `make dev`, run a memo + a chat turn, confirm real (non-"(stub)") output. Keep the key **out of git**
  (`.env` is git-ignored); at deploy it becomes a backend **host secret** only (the UI never holds it).

### 2b. Two-model config (chat = Haiku, memo = Sonnet)
- **`config.py`:** replace the single `generation_model` with two settings (keep a back-compat default):
  - `chat_model: str = "claude-haiku-4-5"`
  - `memo_model: str = "claude-sonnet-4-6"`
- **`core/llm.py`:** `build_llm(settings, model)` (or `build_chat_llm` / `build_memo_llm`) so the provider
  client is built per surface; `LLM_PROVIDER=stub` still returns `StubLLM` for both (offline/CI unchanged).
- **`api/main.py` lifespan:** build `app.state.chat_llm` and `app.state.memo_llm`; `get_llm` splits into
  `get_chat_llm` / `get_memo_llm`. `/analyze` uses the memo (Sonnet) client; `/chat` uses the chat
  (Haiku) client. `/health` reports both model names.
- **Re-verify both model IDs at build** (§0). Update `generation_model` references in `/health` + SPEC.
- Tests: stub path unchanged (both clients are `StubLLM` under `LLM_PROVIDER=stub`); add a small test that
  `/analyze` and `/chat` resolve their respective model settings.

### 2c. Memo rate limit (Sonnet cost cap) — chat stays unlimited
- **Where:** a FastAPI dependency on **`/analyze` only** (not `/chat`).
- **Mechanism (in-memory, stateless-safe):** a module-level counter keyed by client IP → `(date, count)`;
  on each `/analyze`, roll the date over at UTC midnight, increment, and raise **`HTTPException(429)`**
  with a clear `detail` once `count > MEMO_DAILY_LIMIT_PER_IP`. Stores counts only (no inputs), resets on
  restart — consistent with the statelessness invariant.
- **Config:** `memo_daily_limit_per_ip: int = 2` (env-overridable; the Asteroid-Bonanza pattern).
- **Client IP behind Railway's proxy:** prefer the first IP in `X-Forwarded-For`; fall back to
  `request.client.host`. **Caveat:** XFF is spoofable if the host doesn't strip/set it — confirm Railway
  sets a trustworthy XFF; otherwise the limit is best-effort (acceptable for cost control, not security).
- **Single-instance caveat:** the in-memory counter is per-process; keep the backend at one instance, or
  move to a shared store / hosting-layer limit if it ever scales (noted in `phase-5-deploy.md` §13).
- **UI handling (`ui/client.analyze`):** map **429** to a friendly `APIError` ("You've reached today's
  memo limit (N/day). Chat is unlimited, or try again tomorrow."); the memo page already renders
  `APIError` via `st.error`.
- **Chat:** explicitly **no** limit (Haiku is cheap; the builder is fine with unlimited).
- Tests: `/analyze` returns 429 after the limit (override the limit to 1 in a test; assert the (N+1)th
  call is 429 and the message is friendly); `/chat` is never limited; `get_meta`/`/health` unaffected.

---

## 3–9. Deploy steps

Follow `phase-5-deploy.md` §§9–13 in the build order above (embeddings decision, backend deploy + secrets,
UI deploy, CORS, static landing, optional domain, README, `.gitattributes`). The only behavior new to
Phase 5 beyond deploy mechanics is the generation batch (§2); the rest is config + hosting. Record the
resolved embedding choice, the real two-service monthly cost, and the final URLs in §10.

---

## 10. As-built notes

**Chat-quality guardrail — DONE 2026-06-20 (before the two-model/rate-limit step).** Prompted by a Haiku
chat answer that inverted who CT's subscription rules bind and missed that AERDT governs employment
*decisions*, not an employee's tool use. Fix (all offline, 99 tests green):
- **Deterministic law-facts card** (`render_law_facts` from corpus metadata) injected into both chat and
  memo prompts — surfaces operative term, regulated parties, covered domains, and the key-obligation
  labels (which encode *who is bound*). Models are told it's authoritative background, **not** a citable
  source (cite statute sections). Threaded `laws` through `chat`/`chat_stream` + `/chat`.
- **Chat lane + hand-off:** chat answers general statutory questions but declines a definitive personal
  applicability verdict and points situation-specific questions to the Memo; visible `st.info` nudge on
  the chat page. Chat retrieval `k` 5→8.
- **Verified in the running app:** the same remote-CT-employee question now gets the who's-bound and
  tool-use-vs-decision points right on Haiku. **Known gap:** retrieval still pulls subscription/companion
  sections over AERDT (the facts card compensates) — a Phase 8 hybrid-retrieval item, not a v1 blocker.

*(Remaining Phase 5 step-1 work: two-model split (memo→Sonnet) + memo rate limit — §2b/§2c.)*

## 10b. As-built notes

**Two-model split + memo rate limit — DONE 2026-06-20 (steps 2b/2c). 101 tests green.**
- **2b two-model:** `config.py` now has `chat_model="claude-haiku-4-5"` + `memo_model="claude-sonnet-4-6"`
  (was one `generation_model`). `build_llm(settings, model)`; the API lifespan builds `chat_llm` + `memo_llm`;
  `get_chat_llm`/`get_memo_llm` deps; `/analyze` → memo (Sonnet), `/chat` → chat (Haiku); `/health` reports
  both (`HealthResponse.chat_model`/`memo_model`). Model IDs per the `claude-api` skill (Haiku 4.5 ~$1/$5,
  Sonnet 4.6 ~$3/$15) — re-confirm at deploy.
- **2c rate limit:** `memo_rate_limit` dependency on `/analyze` only — in-memory per-IP daily counter
  (`_memo_counts`), `memo_daily_limit_per_ip` default **2** (0 disables); 429 with a friendly message; chat
  unlimited. IP via first `X-Forwarded-For` hop, socket fallback (best-effort, spoofable). Stateless-safe
  (counts only, resets on restart); per-process so backend stays single-instance for v1. UI
  (`ui/client.analyze`) maps 429 to the server's message. Tests: an autouse counter-reset fixture + a
  dedicated 429 test + a UI-client 429 test.
- **Per-user quota + counter (Option 3, added 2026-06-20):** the per-IP limit was effectively *global*
  because the API only sees the UI server, not the browser. Fix: the UI reads the browser IP
  (`st.context.ip_address`, 1.58) and forwards it as an **`X-Client-IP`** header; the API's `_client_ip`
  prefers that header, so the limit and quota key **per end user**. New read-only **`GET /memo-quota`**
  (`{limit, used, remaining}`, no increment) drives a small caption on the memo page ("N of 2 compliance
  memos left today"), rendered via an `st.empty()` placeholder so it reflects the just-generated count.
  Tests: per-user independence (`/memo-quota` for two `X-Client-IP`s) + header-forwarding + decrement.
  Caveat: `X-Client-IP` is spoofable (cost control, not security); `st.context.ip_address` reliability
  behind Railway is the thing to confirm in the live deploy.
- **Verify in the running app** (needs the key): a memo should read at Sonnet quality; the memo page shows
  "N of 2 … left today" and decrements after each generate; the 3rd in a day 429s with the friendly message.

*(Remaining Phase 5: deploy to Railway + secrets, UI deploy + CORS, static
landing, optional domain, README, .gitattributes — §§3–9.)*

## 10c. As-built notes

**Step 2 — production embeddings + index-on-boot — DONE 2026-06-20. 104 tests green.**
- **Embeddings decision: stay LOCAL (fastembed BGE-small, `BAAI/bge-small-en-v1.5`).** §9 framed "local"
  as the heavy option, but the build uses **fastembed (ONNX), not sentence-transformers/PyTorch** — actual
  footprint is onnxruntime ~57MB + the BGE-small ONNX model (~130MB, downloaded once to cache), **no
  torch**. Lighter than the OpenAI alternative would be worth: OpenAI embeddings would add a 2nd API key +
  dependency, a per-query network hop, a full corpus re-embed, and would send **every user query** out to
  OpenAI — against the "we don't store / minimal external exposure" positioning. Local keeps queries
  embedded in-process; only the generation call leaves the box. Re-confirm the model downloads/caches OK in
  the Railway container at deploy (first-boot download; always-on means few cold starts).
- **Index-on-boot (real gap, now fixed):** §9 *assumed* the backend rebuilds the index at startup, but the
  lifespan never did — it opened the (possibly empty) Chroma collection without loading. Since `.chroma/`
  is git-ignored, a fresh Railway container would have booted with an **empty** collection → ungrounded
  memos/chat. Fix: the lifespan now runs `load_corpus` when `store.count() == 0` (idempotent — deterministic
  chunk IDs, skipped when an index already exists, so local dev is untouched). Verified against a fresh
  empty `CHROMA_PATH`: boot logs `built corpus index: 50 chunks`, `/health` reports `corpus_size: 50`.

- *(Record: the re-verified model IDs/pricing; the exact config/llm split shape shipped; the rate-limit
  number + the XFF/IP decision + whether single-instance held; the embeddings choice; the live URLs;
  the measured two-service monthly cost; any `.gitattributes` change.)*

> **Post-deploy (tracked, not Phase 5):** multi-agent memo (per-law analysts + grounding/hedge reviewer)
> — ROADMAP §6 post-v1 backlog. Do not build before v1 is live (binding rule 1).
