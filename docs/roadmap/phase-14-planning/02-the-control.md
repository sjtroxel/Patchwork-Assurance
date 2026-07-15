# 02 — The control: what Patchwork itself runs

*Answers the question "what are the parameters of the memo Patchwork generates?" The control has to be
frozen, recorded, and reproducible, or none of the comparison means anything.*

---

## 1. The control is the production default, unchanged

The whole point of the benchmark is to test **what Patchwork actually ships**, not a tuned-for-the-demo
variant. So the control arm is the production default exactly as a real user gets it:

| Parameter | Value | Where it lives |
|---|---|---|
| `memo_pipeline` | `multi_agent` | `config.py` (flipped to default 2026-07-02, `56c21d8`) |
| `analyst_model` | `claude-sonnet-5` | `config.py` |
| `reviewer_model` | `claude-opus-4-8` | `config.py` |
| `reviewer_max_revisions` | default | `config.py` |
| `retrieval_mode` | `filtered` | `config.py` (Phase 8 batch 6: chosen *from* the numbers) |
| retrieval `k` | `MEMO_RETRIEVAL_K` = 8 | `core/memo.py` |
| embedding model | bge-small | pinned on the Chroma collection |
| corpus | 12 laws / 7 jurisdictions | `corpus/` |
| `corpus_as_of` | max `retrieved_on` across corpus | stamped on the memo |

The entry point is `generate_memo(situation, scope, retriever, llm, laws)` — the same call the API,
the MCP server, and the eval harness all make. Nothing bespoke.

**Do not tune anything for this run.** If a knob gets changed to improve the control's numbers, the
benchmark stops being a measurement of the shipped product and becomes an ad. If you find yourself
wanting to tune, that's a finding for a later phase, not a change to this one.

## 2. The Phase-12 numbers are stale — the control must be re-run

This is easy to miss and would be an expensive mistake.

The Phase-12 paid eval (2026-07-02, $10.55) produced the numbers you know: multi-agent groundedness
97.9%, citations 100%, coverage 78.4%, on **25 in-scope cases**. It is tempting to reuse that as the
Patchwork arm for free.

You can't, because **the corpus changed immediately afterward**:

- 2026-07-02: CT CTDPA + CO CPA added
- 2026-07-03: IL AIVIA + NJDPA added, TX TRAIGA added
- Gold set is now **44 cases** (it was smaller then)
- Two grounding bugs were fixed on 7/3 (key-obligations retrieval pin, NJ citation regex)

So the 7/2 numbers describe a different system against a different gold set. Reusing them would be
comparing a June Patchwork to a July frontier model. **Budget for a fresh control run**
(`07-cost-model.md` accounts for it).

Silver lining: the 7/2 run is still a useful *historical* reference point, and "my own system's numbers
moved when the corpus grew" is an honest aside about why you re-measure instead of quoting.

## 3. Input symmetry: the asymmetry you have to engineer away

Here is a subtle unfairness baked into the current setup.

**Patchwork gets structured input.** The gold cases carry a `situation` dict with clean fields:

```yaml
situation:
  jurisdictions: [Colorado]
  decision_domains: [employment]
  roles: [deployer]
  ai_use: yes
```

That feeds `applicable_laws()`, a deterministic gate. There is no natural-language understanding step
and nothing to get wrong.

**A frontier model gets prose**, because that's what a person types.

If you hand Patchwork tidy structured fields and hand the baselines a vague paragraph, you have not
compared two systems — you've compared two input formats, and you rigged it. A reader will spot this.

**The fix:** a deterministic `render_situation_prose(situation) -> str` that turns the gold `situation`
dict into one canonical, neutral paragraph. Every arm sees identical facts. Patchwork continues to
consume the structured fields (that *is* its design — the form is the product), but the baselines get a
faithful prose rendering of the same facts, with nothing added and nothing withheld.

Example of the intended rendering:

> "We are a business with employees or applicants in Colorado. We use AI to help make employment
> decisions. We are the deployer of the system, not its developer."

Rules for the renderer:
- **Deterministic.** No LLM. It's a template, committed, reviewable, diffable.
- **Lossless.** Every field in the gold `situation` appears. Nothing is hinted, nothing is omitted.
- **Neutral.** No legal vocabulary that leaks the answer. Do not write "we materially influence a
  consequential decision" — that phrase is Colorado's operative term and hands over the finding. Write
  what a business owner would say.

That last rule matters more than it sounds. The prose renderer is a place where you could accidentally
tip the answer to the baselines (making them look better) or write it stiltedly (making them look
worse). It should be committed and reviewed as carefully as any scoring code, because it is effectively
part of the measurement instrument.

## 4. What the control does *not* get

To keep the comparison honest, the control must not receive anything the baselines don't:

- No hand-picked cases where Patchwork is known to do well (`03` and `07` cover case selection).
- No retries the baselines don't get. The existing `LLMError` skip in `run_judged` applies to all arms
  equally.
- No prompt iteration after seeing the results. Freeze the prompts, then run. Iterating the control's
  prompt against the scoreboard is p-hacking with extra steps.

## 5. What to record

Everything below goes in the results artifact so the run is reproducible by a stranger:

- Full `config.py` values for the control (dump the `Settings` object, minus secrets).
- `corpus_as_of` and the 12 law IDs with their `retrieved_on` dates.
- Git SHA of the repo at run time.
- Run date, and the OpenRouter model IDs with prices as of that date.
- The rendered prose for every case (so anyone can see exactly what each model was asked).

---

*Next: `03-the-priming-conflict.md` — why the baselines need two arms, not one.*
</content>
