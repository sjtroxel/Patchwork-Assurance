# AWS / Bedrock fit sketch (exploratory — not a committed plan)

> Status: a **rough sketch**, banked for when the AWS thread is picked up (after the Phase 13
> LegiScan-vs-Open States question closes). Written 2026-07-12. This is a menu + an honest
> fit-verdict, **not** a phase spec — promote a slice into `ROADMAP.md` + a per-phase
> IMPLEMENTATION doc only when it actually starts. Aligns with the banked memory
> "AWS + Bedrock re-platform direction" (kill the recurring AWS job-eligibility filter, cost-gated).

## The reframe (why "add AWS" is the wrong mental model)

AWS is not a feature you bolt onto Patchwork. It is **where things run and which managed services
they use.** So "put Patchwork on AWS" always means *re-hosting or re-providering a slice* — never
adding an "AWS button." That lens is what decides fit.

The good news is the same lesson as the Open States work: **Patchwork's `core/` seams make the
highest-value AWS piece cheap.** `core/llm.py:build_llm` already swaps providers
(`anthropic` / `openrouter` / `stub`) behind one `LLMClient` Protocol. Adding AWS Bedrock is one
more branch plus one adapter class — architecturally identical to adding a second radar data source.

## The terrain (cheapest / least-disruptive first)

Quick glossary inline, since this is a cold start on AWS.

### Tier 0 — Bedrock as a provider (recommended first move; ~zero redefinition)
*Bedrock = AWS's hosted-LLM service; you call the same Claude models through AWS instead of the
Anthropic API directly — AWS billing, AWS IAM permissions.*

- Add a `BedrockLLM` class conforming to the existing `LLMClient` Protocol and a
  `llm_provider="bedrock"` branch in `build_llm` (via `boto3` `bedrock-runtime`).
- Run the **existing eval harness** through Bedrock → "built and evaluated a RAG app on AWS Bedrock
  with Claude, measured with my own harness." Optionally add Bedrock Titan/Cohere **embeddings** as an
  alternate embedding provider (mirrors the `sentence-transformers` seam) — but that means re-indexing
  Chroma, so it's optional.
- **Cost:** per-token, roughly like the Anthropic API; a small eval run is cents, gated by
  `eval/safety.py:confirm_spend`. No always-on cost.
- **Redefinition: none.** A provider swap behind an existing seam. This is the cleanest, most honest
  "I used AWS" proof, and it hits the Bedrock + RAG + Python keywords the AWS-AI postings filter on.

### Tier 1 — host the API on AWS App Runner (the Railway twin)
*App Runner = run your container always-on, autoscaling, HTTPS, no cold start.*

- The repo already has a Dockerfile, so this is "point AWS at your image." Gains: "deployed a Python
  API on AWS," plus IAM and ECR (AWS's container registry). It is **always-on with no cold start**,
  which fits the stated Railway preference — unlike Lambda. Static landing could move to
  S3 + CloudFront (the Vercel twin).
- **Cost:** ~$5–10/mo for a small always-on instance, comparable to Railway. Cost-gated; run it for a
  demo window or keep one.
- **Redefinition: none.** The AWS twin of the current deploy.

### Tier 2 — AWS-native RAG (optional; résumé-shiniest, but a real trade-off)
Swap Chroma for *OpenSearch Serverless* / *S3 Vectors*, or use *Bedrock Knowledge Bases* (turnkey
RAG: point it at an S3 corpus, it chunks/embeds/retrieves for you).

- **The honest catch:** Knowledge Bases hides the hand-built chunker and retriever behind a managed
  box — and that hand-built retrieval is exactly the engineering the portfolio shows. It trades "shows
  AWS RAG" for "hides my RAG." Do it as a *parallel* demo, never a replacement.
- **Cost footgun:** OpenSearch Serverless has a non-trivial minimum (hundreds/mo if left running) —
  must be ephemeral. This is the free-tier footgun the banked note warned about.
- **Redefinition: moderate** — it starts changing what the app *is*.

## Where AWS genuinely becomes a poor fit (the honest boundary)

- **Cognito (auth) or DynamoDB (a user store):** would break the stateless-by-design privacy feature.
  That *redefines the app*. Don't — and note this is a thing you'd reach for *because* AWS makes it
  easy, which is the trap. (Architecture invariant 3: no auth, no DB, by design.)
- **Full Lambda + API Gateway as the *live app* host:** Lambda scales to zero but cold-starts; a RAG
  app loading an embedding model means multi-second lag on a cold hit — fights the no-cold-start
  preference. Poor fit for the interactive surface. (Aside: the *weekly radar cron* is a perfect
  Lambda fit — batch, scheduled, cold-start irrelevant — if an AWS angle there is ever wanted.)
- **OpenSearch Serverless left always-on:** breaks the ~$0 model.

## Verdict

AWS is **not** a poor match for Patchwork — but only because the seam architecture lets it enter as a
**compute + model-provider swap** (Tiers 0–1), which leaves the app's definition — stateless, grounded,
educational — completely intact. It becomes a poor match the instant AWS is used to add **state or
auth**, or to force cold-start serverless onto the live surface; those change what Patchwork *is*.

Stay in the compute + model lane and AWS slides in cleanly. Wander into the state/auth lane and you've
redefined the app. **When this thread is picked up, Tier 0 (the `BedrockLLM` adapter) is the move** —
highest skill-signal per dollar and per hour, and it reuses the exact adapter pattern the Open States
work establishes.
