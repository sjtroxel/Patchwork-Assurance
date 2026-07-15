# 01 — Model access and the landscape

*Verified live 2026-07-15. The design doc §3 says re-verify at build and record the check date; this
is that check. It will be stale within weeks — that churn is literally the thesis, so re-run the
verification the day the build starts and update this file.*

---

## 1. Access is a solved problem

Every model under consideration is available through **OpenRouter**, which you already fund as your
single API wallet and already have a working client for (`core/llm.py:OpenRouterLLM`, OpenAI-compatible,
`LLM_PROVIDER=openrouter`).

Concretely, that means:

- **One balance**, not four vendor accounts with four cards. (5.5% on top-up, no per-token markup.)
- **One code path.** `OpenRouterLLM` already does structured output with lenient JSON parsing and
  bounded retry/backoff — built during the Phase 8 interlude, hardened when the strict parser turned
  out to be the real bug rather than model quality.
- **No new provider adapter.** Swapping models is a model-ID string, not a class.

This is worth noting in the write-up as an architecture point: the `build_llm` seam is why adding four
rival vendors to this project costs approximately zero engineering. It's the same seam that makes
Bedrock a one-branch adapter (`aws-bedrock-fit-sketch.md`).

## 2. What's actually GA today

Pulled from the live OpenRouter catalog (`GET https://openrouter.ai/api/v1/models`, 342 models) on
2026-07-15, cross-checked against vendor docs.

| Lab | Model ID | $/M in | $/M out | Context | Status |
|---|---|---|---|---|---|
| OpenAI | `openai/gpt-5.6-sol` | $5.00 | $30.00 | 1.05M | **GA (7/9/2026)** |
| Anthropic | `anthropic/claude-fable-5` | $10.00 | $50.00 | 1M | GA |
| Google | `google/gemini-3.5-flash` | $1.50 | $9.00 | 1.05M | GA |
| Google | `google/gemini-3.1-pro-preview` | $2.00 | $12.00 | 1.05M | **preview only** |
| DeepSeek | `deepseek/deepseek-v4-pro` | $0.43 | $0.87 | 1.05M | GA |

For reference, Patchwork's own models on the same catalog: `anthropic/claude-sonnet-5` at $2/$10 and
`anthropic/claude-opus-4.8` at $5/$25.

## 3. Two corrections to the 2026-07-07 list

**GPT-5.6 Sol went GA.** The design doc §3 said "GPT-5.6 'Sol' was gated preview, NOT GA — don't use
until GA." That gate cleared on 2026-07-09. Sol is now self-serve in the API with no plan gating, at
$5/$30 (the same price it carried in preview). The family is Sol (flagship, deepest reasoning) /
Terra ($2.50/$15, balanced) / Luna ($1/$6, volume tier). **Use Sol** — it's the flagship, and the
comparison should be against each lab's best, not its cost-optimized tier.

**Google has no GA Pro model in the 3.x line.** The design doc anticipated "Gemini 3.5 Pro cleared for
July GA." It did not happen. As of today:

- Gemini 3.5 **Pro** does not exist. No model ID, not in the docs, not in the OpenRouter catalog.
- Gemini 3.1 **Pro** exists only as `-preview`.
- Gemini 3.5 **Flash** is GA, and Google's own model docs describe it as their most intelligent model
  for sustained frontier performance.

So Google's GA frontier text model is a *Flash*-tier model. This is awkward and needs a decision.

## 4. The Gemini decision

Three options, none clean:

| Option | Pro | Con |
|---|---|---|
| `gemini-3.5-flash` only | Obeys the doc's "GA only" rule; is genuinely Google's GA frontier line | Invites "you sandbagged Google by using Flash" |
| `gemini-3.1-pro-preview` only | Pro tier, closer to an apples-to-apples flagship | Breaks the GA-only rule; preview models can change under you and aren't reproducible |
| **Both** | Kills the sandbagging objection outright; costs ~$0.41 extra on a 12-case set | One more arm to render in the results table |

**Recommendation: run both.** Headline the GA one (3.5 Flash), footnote the preview one (3.1 Pro). At
roughly forty cents this is the cheapest credibility you will ever buy, and "Google's flagship tier is
preview-only right now, so I ran both and here's the difference" is a *more* informed-sounding note
than quietly picking one.

Whichever way this lands, the write-up must state Google's GA situation explicitly. Silently using
Flash and calling it "Google's frontier model" is the kind of small inaccuracy that a knowledgeable
reader catches and then distrusts the rest of the numbers over.

## 5. The Chinese model: include it, but not for diversity

You floated "maybe something Chinese." The catalog has plenty of live options: DeepSeek V4 Pro
($0.43/$0.87), GLM-5.2 ($0.87/$2.72), Qwen3.7-Max ($1.25/$3.75), Kimi K2.7, MiniMax M3.

Adding one *for national diversity* is a weak reason — it doesn't answer any question the reader has,
and "does a Chinese model know Colorado employment law" is a mildly interesting trivia result, not a
finding.

**The strong reason to include DeepSeek V4 Pro is price-performance.** It is roughly **20x cheaper than
Fable 5** ($0.43/$0.87 vs $10/$50). That sets up the sharpest question in the whole experiment:

> Does a 20x-cheaper model, properly grounded, beat a frontier model asked raw?

That is an *architecture* claim rather than a vendor claim, it's the question a working AI engineer
actually asks, and it is the natural headline for the post. See `08-build-plan.md` on the grounded-cheap
ablation and `09-the-post.md` on why this reframing is stronger.

If you want a second Chinese model as a robustness check, GLM-5.2 at $0.87/$2.72 is the next pick. Not
necessary; nice-to-have.

## 6. The proposed model set

| Arm | Model | Role |
|---|---|---|
| Control | Patchwork multi_agent (Sonnet 5 + Opus 4.8, grounded) | The system under test |
| Baseline | `openai/gpt-5.6-sol` | OpenAI flagship, GA |
| Baseline | `anthropic/claude-fable-5` | Anthropic flagship, GA |
| Baseline | `google/gemini-3.5-flash` | Google GA frontier |
| Baseline | `google/gemini-3.1-pro-preview` | Google Pro tier, disclosed as preview |
| Baseline | `deepseek/deepseek-v4-pro` | Price-performance probe |
| Ablation | `deepseek/deepseek-v4-pro` **+ Patchwork corpus** | Isolates grounding from model quality |

Including Fable 5 is a credibility asset, not a conflict of interest. Patchwork is Claude-powered, so
benchmarking against Anthropic's own best model and reporting that raw Fable 5 loses to a Sonnet-5-based
grounded system is a statement about *grounding*, not about vendors. If Patchwork only beat rival labs
while ducking its own, that would be the suspicious version.

## 7. What to re-verify at build time

- [ ] Re-pull the OpenRouter catalog; confirm every model ID still resolves and the prices still hold.
- [ ] Re-check whether Gemini 3.5 Pro has shipped (it may, and it would replace both Gemini rows).
- [ ] Confirm each model's structured-output support through OpenRouter (`json_schema` in
      `response_format`). Some models silently ignore it; the lenient parser is the fallback. See
      `06-variables-to-pin.md`.
- [ ] Record each model's stated training cutoff — this is load-bearing for the currency finding
      (`05-metric-hierarchy.md` §2).
- [ ] Record the check date in the write-up.

---

*Sources, checked 2026-07-15: OpenRouter live model catalog (`api/v1/models`); Google Gemini API model
docs (`ai.google.dev/gemini-api/docs/models`); OpenAI GPT-5.6 GA coverage
(`digitalapplied.com/blog/gpt-5-6-sol-terra-luna-public-ga`).*
</content>
</invoke>
