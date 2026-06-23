"""Spending guardrails for paid (token-spending) operations.

Defense in depth — several independent layers must each fail before real money burns:

  1. Hard cap     — a paid run may not attempt more than N units (a runaway circuit breaker),
                    no matter how it was invoked.
  2. Unattended   — refuse to spend when stdin is not an interactive terminal (a piped or
                    background invocation), the exact failure mode that cost real money once.
  3. Confirmation — an interactive run still requires a typed 'yes', shown a cost estimate.

These are code-level guards. The real backstop lives at the provider: a monthly spend limit on
the API key in the Anthropic console, so no code path — not even one we haven't written — can
exceed a dollar ceiling. See docs/SPENDING_SAFETY.md.

`confirm_spend` never raises on refusal: it returns False so callers abort cleanly, having spent
nothing.
"""

import sys


def confirm_spend(
    *,
    description: str,
    units: int,
    cap: int,
    est_cost_usd: float | None = None,
) -> bool:
    """Return True only if it is safe to spend. `units` is the count of paid operations (e.g.
    memos to generate); `cap` is the hard ceiling. All three layers below must pass."""
    if units > cap:
        print(
            f"\n  [spend blocked] {description}: {units} paid units exceeds the hard cap of {cap}.\n"
            f"  Raise the cap deliberately (config.eval_max_judged_cases) if you truly mean it.\n"
        )
        return False

    if not sys.stdin.isatty():
        print(
            f"\n  [spend blocked] Refusing to spend without an interactive terminal "
            f"({description}, ~{units} paid units). Run it yourself in a shell.\n"
        )
        return False

    estimate = f"  Rough estimate: ${est_cost_usd:.2f}." if est_cost_usd is not None else ""
    print(f"\n  About to spend API tokens — {description} (~{units} paid units).{estimate}")
    return input("  Type 'yes' to proceed (anything else aborts): ").strip().lower() == "yes"
