# Spending safety

This project calls paid LLM APIs. A careless command can spend real money fast. The guardrails
below are **defense in depth**: several independent layers, so no single slip drains the budget.
This page is also a transferable checklist — the same layering belongs in any project that spends
on inference, including ones with an employer's budget attached.

## The incident this came from

A `python -m eval.run --judge` was run to "check that it skips gracefully." The skip only happens
under `LLM_PROVIDER=stub`; the local `.env` had `LLM_PROVIDER=anthropic`, so the command went
straight to the paid path and generated real memos + judge calls before it was caught. It cost real
money. Every layer below exists to make that specific failure impossible to repeat.

## Layer 1 — Provider-side spend limit (the real backstop)

Code guards can be bypassed by code we haven't written yet. The only guard that holds against
*every* path is at the provider:

- In the Anthropic console, set a **monthly spend limit** on the workspace/organization, low enough
  that the worst case is an annoyance, not a disaster.
- Use a **dedicated, low-limit API key for development**, separate from anything production.
- (Verify the exact console location yourself — the billing/limits UI moves around.)

This is the one guard a real employer will also rely on. Set it once; it protects you from yourself
and from any tool you run.

## Layer 2 — Code-level chokepoint (`eval/safety.py:confirm_spend`)

Every paid batch in this repo routes through one function, so the guard can't be forgotten in a new
code path. It enforces, in order:

1. **Hard cap** — a run may not attempt more than `config.eval_max_judged_cases` paid units (a
   runaway circuit breaker). Over the cap, it refuses before prompting.
2. **No unattended spend** — if stdin is not an interactive terminal (a piped or background
   invocation, as in the incident), it refuses outright.
3. **Typed confirmation** — an interactive run still requires a typed `yes`, shown a rough cost
   estimate first.

A future paid path (e.g. the Phase 9 agent) should call `confirm_spend` too, not reinvent the gate.

## Layer 3 — Operating rule: paid runs are the human's to execute

The AI assistant treats token-spending commands the way it treats `git`: **it never runs them.** It
provides the command; the human runs it, in their own terminal, when they intend to spend. Free
commands (`make eval`, `make test`) are fine to run anytime; anything that spends (`make eval-judge`)
is hand-off only.

## Checklist for any spending project

- [ ] A provider-side monthly spend limit is set, low enough to be safe.
- [ ] Dev uses a separate, low-limit key — never the production key.
- [ ] Every paid code path goes through one confirmation chokepoint (cap + no-unattended + confirm).
- [ ] The default mode is free/stubbed; spending is explicit opt-in, never the default.
- [ ] A cost estimate is shown before any confirmed spend.
- [ ] The assistant hands off paid commands; the human runs them.
