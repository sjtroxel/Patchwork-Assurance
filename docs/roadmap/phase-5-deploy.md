# Phase 5 — Deploy + README (the v1 finish line)

*Phase plan (intended design), written 2026-06-17. Final phase of v1 (ROADMAP §6). Deploys all three
surfaces — the static landing page, the Streamlit UI, and the FastAPI backend — wires them across
origins, writes the public README, and lands the Python-dominant `.gitattributes` backstop. Hosting
facts below were **web-verified June 2026**; re-verify at deploy (pricing/limits churn — ROADMAP
standing rule). When this ships, v1 is public and Phases 6+ unlock. The as-built companion
`phase-5-deploy-IMPLEMENTATION.md` is written when the phase begins.*

> **Revised 2026-06-19 by Phase 4.5.** Two things in this doc were superseded by
> [`phase-4.5-visual-identity-and-front-door.md`](phase-4.5-visual-identity-and-front-door.md) §9, §11
> and are corrected inline below: (1) **the UI host moved from Streamlit Community Cloud to always-on
> Railway** (Community Cloud sleeps behind a manual wake button and refuses custom domains), so there is
> no hibernation to "accept"; and (2) **a third surface** — the static landing-page front door — joins
> the topology, and a custom domain can put all of it under one umbrella. Where older text still says
> "Streamlit Community Cloud / hibernation accepted," Phase 4.5 is controlling.

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

- [ ] The **static landing page** (Phase 4.5) is live on a free static host (Vercel/Railway static),
      reachable over HTTPS, with the "Launch the tool" CTA pointing at the live Streamlit app.
- [ ] The Streamlit UI is live on **Railway (always-on)** from the public GitHub repo, reachable over HTTPS.
- [ ] The FastAPI backend is live on **Railway**, reachable over HTTPS.
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
- **No keep-alive hacks, no hibernation to accept.** Phase 4.5 put the UI on always-on Railway, so the
  free-tier-sleep problem is gone (not papered over). The static landing page is on a CDN and never sleeps.

---

## 4. Deploy topology — two services, two URLs

```
  recruiter / user
        │  https://patchworkassurance.com (apex)   → static landing page   (free static host, INSTANT)
        ▼  "Launch the tool →"
   Streamlit UI  https://app.patchworkassurance.com   (Railway, always-on)
        │  ──HTTPS──►  FastAPI backend                (Railway, always-on)
        │  (settings.api_base_url)  https://api...
        ▼                                 │ imports
                                          ▼
                          core/  +  Chroma index (rebuilt at startup)
```

Three surfaces now (Phase 4.5): a static landing front door, the Streamlit UI, and the API. UI and API
both run **always-on on Railway** (no cold-start to accept); the landing page is static CDN. The
config-driven `api_base_url` (Phase 0 §5.3) makes the UI point at `localhost` in dev and the deployed
backend in prod with no code change. Custom domain optional (~$12/yr); until then the `…vercel.app` /
`…railway.app` URLs work, carried by shared branding (Phase 4.5 Track C).

---

## 5. The hosting decision (verified June 2026)

**Frontend — Streamlit UI on Railway (decided 2026-06-19, Phase 4.5 §9).** Superseded the original
Streamlit Community Cloud choice. Community Cloud is free but **hibernates after ~12h** behind a manual
"wake" button and **refuses custom domains** — both verified 2026-06-19. Railway runs the same Streamlit
process **always-on** (no hibernation, no wake button) and supports custom domains, so the UI joins the
API on the existing Railway project. **Landing page** (Phase 4.5) deploys to a free **static** host
(Vercel lead, or Railway static) — CDN, instant, never sleeps.

**Backend — a real $0-vs-~$5/mo decision, not a free lunch:**

| Option | Cost | Cold-start | Notes |
|---|---|---|---|
| **Railway Hobby** | **~$5/mo** ($5 base incl. $5 usage) | none (always-on) | The builder's lead choice; hosted Heritage Odyssey's FastAPI. Railway's "Free" plan is only $1/mo credit — too small for an always-on backend. |
| **Hugging Face Spaces (free)** | $0 | sleeps when idle | True $0, but the backend cold-starts on wake. |
| **Render (free)** | $0 | slow cold-start | Explicitly disliked (the spin-up). Listed for completeness; not recommended. |

**The nuance, as resolved by Phase 4.5:** the original plan accepted a hibernating free Streamlit
Community Cloud UI. Verification on 2026-06-19 showed that hibernation hides behind a manual wake button
(a GET won't wake it) and that Community Cloud refuses custom domains — both poor for a portfolio demo.
Since the builder already runs Railway, hosting the **UI there too** makes the whole app always-on and
brings custom domains back. The hibernation tradeoff simply goes away.

**Decided — all hosts settled (2026-06-17 backend; 2026-06-19 frontend):**
- **Backend: Railway Hobby, an *already-active* subscription** (also hosted Heritage Odyssey), always-on,
  cost sunk ([[feedback-deploy-hosting-preferences]]).
- **Frontend: Streamlit UI on Railway too** (Phase 4.5 §9) — always-on, custom-domain capable. Keeps the
  **deployed full-stack *Python* app** portfolio signal (ROADMAP §3) while killing the cold-start.
- **Landing page: free static host** (Vercel/Railway static) — $0, instant.

So v1 runs on the **already-active Railway Hobby ($5/mo base)** plus **usage** — two always-on services
may run a few dollars over the included $5 credit (verify at deploy) — with a **$0** static landing
page. The only genuinely new spend is an optional **~$12/yr** custom domain.

---

## 6. Cross-origin wiring

Two URLs means a genuine cross-origin call, the thing that silently breaks first-time deploys:

- The UI's `api_base_url` (Streamlit secret / env) is set to the **deployed backend URL**, not
  `localhost`.
- The backend's `CORSMiddleware` (wired in Phase 3 §8) must allow the **Streamlit app origin** — now the
  Railway UI URL (`app.patchworkassurance.com` / `…railway.app`), not a `streamlit.app` URL. Set
  `cors_allow_origins` via a host env var. (The static landing page does not call the API — it only
  links to the app — so it needs no CORS entry.)
- Verify with the deployed `/health` from the UI before calling it done — a CORS or wrong-URL failure
  shows up here, not in local `make dev`.

---

## 7. Secrets and env config (the learning)

- **`ANTHROPIC_API_KEY`** lives only as a **host secret** on the backend (Railway/HF secret manager),
  never committed (already git-ignored). The UI never holds it — only the backend calls Claude.
- **The UI** holds only `api_base_url` (and nothing sensitive), via the Railway service's env vars.
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

- **Landing page:** $0 (static host — Vercel/Railway static, CDN, never sleeps).
- **UI + Backend:** both always-on on **Railway Hobby ($5/mo base + usage)** — two services may run a few
  dollars over the included $5 credit; verify the real bill at deploy.
- **Generation:** `claude-haiku-4-5`, well under a cent per memo (Phase 2 §10).
- **Embeddings:** $0 local, or a fraction of a cent total for OpenAI `text-embedding-3-small` (§9).
- **Net:** the **already-active Railway Hobby ($5/mo base)** + modest usage for the second always-on
  service; **$0** landing page; an optional **~$12/yr** custom domain is the only genuinely new spend.
  No hibernation, no wake delay — the always-on Railway UI is the deliberate upgrade over the original
  free-but-sleeping Streamlit Cloud plan.

## 11. Intended build order

1. Production embedding decision (§9); confirm the loader rebuilds the index at startup.
2. Deploy the **backend** to Railway: set `ANTHROPIC_API_KEY` (+ embedding key) as secrets; confirm
   `/health` over HTTPS.
3. Deploy the **Streamlit UI** to Railway (always-on) from the public repo; set `api_base_url` to the
   backend URL.
4. Set backend `cors_allow_origins` to the Railway UI URL; verify the cross-origin call from the live UI.
5. Deploy the **static landing page** (Phase 4.5 `site/`) to the static host; point its "Launch" CTA at
   the live UI URL.
6. (Optional, tail) attach the custom domain: apex → landing, `app.` subdomain → the Railway UI.
7. End-to-end smoke in public: landing → launch → memo path + streamed chat, chrome present, disclaimer
   present.
8. Write the public README (§8); add the `.gitattributes` Python-dominant backstop (incl. `site/**`).
9. Final pass: the live demo works, the README reads clean, language stats read Python.

## 12. `.gitattributes` — Python-dominant backstop

The stack is all Python, so GitHub *should* read Python-dominant on its own; `.gitattributes` is the
backstop for edge cases (mark `docs/**` and `corpus/**` as `linguist-documentation`). The new variable
is the Phase 4.5 landing page (`site/**` — HTML/CSS/JS): **measure the byte ratio first** (Phase 4.5
§10), and only if it threatens the Python-dominant bar, mark `site/**` `linguist-documentation` too.
Keep it minimal — it exists to protect the deliberate "I build in Python" signal (ROADMAP §3), not to
micromanage.

## 13. Open decisions for this phase

- ~~Backend host~~ **Decided: Railway Hobby** (already an active subscription, §5). ~~Streamlit Cloud for
  the UI, hibernation accepted~~ — **superseded 2026-06-19: the UI is on always-on Railway too** (Phase
  4.5 §9); landing page on a free static host. Open sub-item: landing host = Vercel vs Railway static
  (minor, decide at deploy).
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
