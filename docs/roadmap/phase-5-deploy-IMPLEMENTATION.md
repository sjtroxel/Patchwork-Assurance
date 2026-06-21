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

## 10b. As-built notes (fill during the rest of the build)

- *(Record: the re-verified model IDs/pricing; the exact config/llm split shape shipped; the rate-limit
  number + the XFF/IP decision + whether single-instance held; the embeddings choice; the live URLs;
  the measured two-service monthly cost; any `.gitattributes` change.)*

> **Post-deploy (tracked, not Phase 5):** multi-agent memo (per-law analysts + grounding/hedge reviewer)
> — ROADMAP §6 post-v1 backlog. Do not build before v1 is live (binding rule 1).
