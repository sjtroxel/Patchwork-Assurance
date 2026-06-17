# Phase 5 — Deploy + README (the v1 finish line)

*Phase plan (intended design), written 2026-06-17. Final phase of v1 (ROADMAP §6). Puts the UI on
Streamlit Community Cloud and the FastAPI backend on a chosen host, wires them across origins, writes the
public README, and lands the Python-dominant `.gitattributes` backstop. Hosting facts below were
**web-verified June 2026**; re-verify at deploy (pricing/limits churn — ROADMAP standing rule). When
this ships, v1 is public and Phases 6+ unlock. The as-built companion `phase-5-deploy-IMPLEMENTATION.md`
is written when the phase begins.*

---

## 1. What Phase 5 is

Shipping. The two-service app that works on `make dev` goes live at two public URLs, with a README that
frames it honestly, and the repo reads Python-dominant on GitHub.

This is the gate in binding rule 1 (ROADMAP §1): **nothing in Phases 6+ is built until this phase is
done and the app works end to end in public.** Evals, observability, hybrid retrieval, the monitoring
agent, MCP — all of it waits behind a live URL.

**Primary learning (ROADMAP §6):** deploy, secrets, env config.

---

## 2. Definition of done

- [ ] The Streamlit UI is live on `*.streamlit.app` (custom subdomain `patchwork-assurance` if free) from
      the public GitHub repo.
- [ ] The FastAPI backend is live on its host (Railway or a free host — §5), reachable over HTTPS.
- [ ] The UI's `api_base_url` points at the deployed backend; **CORS** lets the UI origin call it; the
      end-to-end demo path works in public: type a situation → grounded memo with citations; ask a
      follow-up → streamed grounded answer.
- [ ] `ANTHROPIC_API_KEY` (and any embedding key) live only as **host secrets**, never in the repo.
- [ ] The corpus index exists on the backend — **rebuilt at startup** from the committed corpus files
      (§9), since `.chroma/` is git-ignored.
- [ ] The real **public README** replaces the minimal one (§8): what it is, architecture, run-locally,
      not-legal-advice, the honest J.D. framing.
- [ ] A `.gitattributes` backstop so GitHub language stats read Python-dominant (§10).
- [ ] A deployed `/health` smoke check passes (corpus size + models live).

Done = **v1 is deployed, public, and works.** This is the finish line.

---

## 3. Explicitly NOT in Phase 5

- **No new features.** Deploy what Phases 0–4 built. If something's missing, it's a v1 scope cut, not a
  Phase 5 addition.
- **No evals/observability/security hardening/hybrid retrieval/agent/MCP** — all Phases 6+ , gated
  behind this shipping.
- **No auth, no database, no saved history** (ROADMAP §8) — still stateless in production. The
  "we don't store your inputs" line is now literally true on a public URL.
- **No always-on guarantee for free.** See §10 — free tiers sleep; that's accepted for v1.

---

## 4. Deploy topology — two services, two URLs

```
  recruiter / user
        │  https://patchwork-assurance.streamlit.app   (Streamlit Community Cloud, free)
        ▼
   Streamlit UI ──HTTPS──►  FastAPI backend            (Railway ~$5/mo, or a free host)
   (settings.api_base_url) https://<backend-host-url>
                                 │ imports
                                 ▼
                          core/  +  Chroma index (rebuilt at startup)
```

The two-service split (ROADMAP §3) means two deploys and two cold-starts — honestly accepted. The
config-driven `api_base_url` (Phase 0 §5.3) is what makes the UI point at `localhost` in dev and the
deployed backend in prod with no code change.

---

## 5. The hosting decision (verified June 2026)

**Frontend — Streamlit Community Cloud (decided).** Free, deploys straight from the public repo
(points at `src/patchwork_assurance/ui/app.py`), redeploys on push, custom subdomain on `streamlit.app`
(`patchwork-assurance` is within the 6–63 char limit). **It hibernates after ~12h of no traffic** and
wakes with a delay — so even the free frontend has a cold-start. Vercel is not an option (can't host a
long-lived Streamlit server).

**Backend — a real $0-vs-~$5/mo decision, not a free lunch:**

| Option | Cost | Cold-start | Notes |
|---|---|---|---|
| **Railway Hobby** | **~$5/mo** ($5 base incl. $5 usage) | none (always-on) | The builder's lead choice; hosted Heritage Odyssey's FastAPI. Railway's "Free" plan is only $1/mo credit — too small for an always-on backend. |
| **Hugging Face Spaces (free)** | $0 | sleeps when idle | True $0, but the backend cold-starts on wake. |
| **Render (free)** | $0 | slow cold-start | Explicitly disliked (the spin-up). Listed for completeness; not recommended. |

**The honest nuance that decides it:** paying ~$5/mo for Railway makes the *backend* always-on, but the
**Streamlit UI still hibernates after 12h** on the free tier — so the very first hit after a long idle
still pays a wake delay on the frontend regardless. For a portfolio demo visited occasionally, $5/mo
buys a snappier backend but does **not** eliminate cold-start end to end.

**Decided 2026-06-17 — both hosts settled, and the $0-vs-paid tension dissolves:**
- **Backend: Railway Hobby (~$5/mo), an *already-active* subscription.** The builder already pays for
  Railway Hobby (it also hosted Heritage Odyssey), so the backend is always-on by default and the cost
  is sunk — not a new line item. Railway is the confirmed backend host
  ([[feedback-deploy-hosting-preferences]]).
- **Frontend: Streamlit Community Cloud, accepting the ~12h hibernation.** The builder dislikes the
  wake delay but judges it a worthwhile, deliberate tradeoff: the goal is a **deployed full-stack
  *Python* app** in the portfolio (the Python-dominant signal, ROADMAP §3), and Streamlit Cloud is the
  free, purpose-built way to get it. The cold-start is accepted as the price of that.

So v1 runs at **~$5/mo** (the Railway subscription already in place) with a **$0 frontend**; the only
thing the sleep costs is a first-visit wake delay, which is accepted. No new spend, no decision left
open here.

---

## 6. Cross-origin wiring

Two URLs means a genuine cross-origin call, the thing that silently breaks first-time deploys:

- The UI's `api_base_url` (Streamlit secret / env) is set to the **deployed backend URL**, not
  `localhost`.
- The backend's `CORSMiddleware` (wired in Phase 3 §8) must allow the **Streamlit app origin**. Set
  `cors_allow_origins` to the `streamlit.app` URL via a host env var.
- Verify with the deployed `/health` from the UI before calling it done — a CORS or wrong-URL failure
  shows up here, not in local `make dev`.

---

## 7. Secrets and env config (the learning)

- **`ANTHROPIC_API_KEY`** lives only as a **host secret** on the backend (Railway/HF secret manager),
  never committed (already git-ignored). The UI never holds it — only the backend calls Claude.
- **The UI** holds only `api_base_url` (and nothing sensitive), via Streamlit Cloud's secrets.
- If production embeddings use OpenAI (§9), its key is a backend secret too.
- This is the "secrets, env config" rep: same code, different config per environment, no key in git.

---

## 8. The public README

Replace the minimal placeholder with the real thing — honest portfolio framing, **not** hackathon
scaffolding (the lesson from Daniel's repo review):

- **What it is** (one paragraph): an AI-native tool for understanding the state-by-state AI-regulation
  patchwork, grounded in primary statutory text, architected to add jurisdictions/evals/an agent
  additively.
- **Live demo** link + a screenshot or short clip.
- **Architecture** (a few lines / one diagram): `core/` keystone, FastAPI, Streamlit, Chroma; the four
  seams in a sentence.
- **Repository map** and **run-locally** (`make install && make dev`) — the useful parts of Daniel's
  README, not the Judge-Score-Map parts.
- **Not legal advice** + the honest **J.D. framing** (narrow edge, not a credential claim; third-person,
  sanitized per [[project-legal-repo-public-prep-and-kevin]]).
- **Built to demonstrate** RAG/agent engineering on a real, current legal corpus.

The detailed README structure is its own small task at deploy time; this is the checklist.

---

## 9. Production index + embeddings (a real deploy gotcha)

- **The Chroma index isn't in the repo** (`.chroma/` is git-ignored). The committed **corpus `.md` +
  `.meta.yaml`** are, so the backend **rebuilds the index at startup** by running the Phase 1 loader in
  the FastAPI lifespan if the index is absent. A 2-statute corpus rebuilds fast — fine on boot.
- **Embedding model on the host** is the open call (Phase 1 §11, ROADMAP §10):
  - *Local `sentence-transformers`* — free, but the model weights (~hundreds of MB) download/load into
    the container, inflating image size and cold-start on small free hosts.
  - *OpenAI `text-embedding-3-small`* — pennies and no heavy local model (lighter container, faster
    boot), at the cost of a second API key + dependency.
  - Decide at deploy weighing container/cold-start vs the tiny API cost + one-key simplicity. Query and
    corpus embeddings must use the **same** model (the Phase 1 §6.3 guard still applies in prod).

## 10. Cost model (verified June 2026)

- **Frontend:** $0 (Streamlit Community Cloud), sleeps after ~12h idle.
- **Backend:** $0 on HF Spaces free (sleeps), or **~$5/mo** on Railway Hobby (always-on). Render free
  works but is the disliked slow-cold-start path.
- **Generation:** `claude-haiku-4-5`, well under a cent per memo (Phase 2 §10).
- **Embeddings:** $0 local, or a fraction of a cent total for OpenAI `text-embedding-3-small` (§9).
- **Net:** **~$5/mo total** — the Railway Hobby subscription the builder *already* pays — plus a $0
  Streamlit frontend. **v1 incurs no new spend.** The only cost of the free frontend is the
  first-visit wake delay, accepted as the price of a deployed full-stack Python portfolio app.

## 11. Intended build order

1. Production embedding decision (§9); confirm the loader rebuilds the index at startup.
2. Deploy the **backend** first (Railway or HF): set `ANTHROPIC_API_KEY` (+ embedding key) as secrets;
   confirm `/health` over HTTPS.
3. Deploy the **UI** to Streamlit Cloud from the public repo; set `api_base_url` to the backend URL.
4. Set backend `cors_allow_origins` to the `streamlit.app` URL; verify the cross-origin call from the
   live UI.
5. End-to-end smoke in public: memo path + streamed chat, chrome present, disclaimer present.
6. Write the public README (§8); add the `.gitattributes` Python-dominant backstop.
7. Final pass: the live demo works, the README reads clean, language stats read Python.

## 12. `.gitattributes` — Python-dominant backstop

The stack is all Python, so GitHub *should* read Python-dominant on its own; `.gitattributes` is the
backstop for edge cases (mark `docs/**` and `corpus/**` as `linguist-documentation`, the inline-HTML
footer string and any config as not skewing the stats). Keep it minimal — it exists to protect the
deliberate "I build in Python" signal (ROADMAP §3), not to micromanage.

## 13. Open decisions for this phase

- ~~Backend host~~ **Decided: Railway Hobby** (already an active subscription, §5). Streamlit Cloud for
  the UI, hibernation accepted.
- **Production embeddings: local vs OpenAI** (§9) — container/cold-start vs pennies + one key. The one
  genuinely open infra decision left for deploy.
- **README depth** — ship a solid v1 README; iterate later. Don't gold-plate it before the app is live.

## 14. What shipping this means

- **v1 is done.** The app is public, grounded, and works end to end; the repo reads Python-dominant; the
  README frames it honestly. This is the portfolio asset and the job-search artifact (ROADMAP §1
  binding rule 3).
- **Phases 6+ unlock.** Only now: evals (Phase 6), observability + security (7), hybrid retrieval (8),
  the monitoring/ingestion agent (9), MCP (10) — measure, harden, improve, then build the self-updating
  engine on proven infrastructure (ROADMAP §6 ordering rationale).
- **Post to it.** Definition of "shipped" includes it being posted/linkable — the build loop feeding the
  activation loop, which is the whole point.
