"""Per-token pricing in one place — rates churn, so this is the single spot to update
(Phase 7 IMPLEMENTATION §3).

Rates verified 2026-07-01 via the `claude-api` skill. Re-verify at build.

The four Anthropic `usage` fields are **additive**: total prompt tokens =
`input_tokens + cache_read_input_tokens + cache_creation_input_tokens`, where `input_tokens` is only the
UNCACHED remainder. So each tier is billed at its own rate below — never treat `input_tokens` as the whole
prompt (that under-bills a cached request and overstates the cache win).
"""

# model -> (input $/1M tokens, output $/1M tokens)
RATES: dict[str, tuple[float, float]] = {
    # The offline stub is GENUINELY free, so it is priced at zero rather than left unknown. Without
    # this, every $0 dry run trips the unpriced-call warning and the warning stops meaning anything
    # by the time a real run needs it.
    "stub": (0.0, 0.0),
    "claude-haiku-4-5": (1.0, 5.0),
    # Sonnet 5 intro pricing $2/$10 per Mtok through 2026-08-31, then $3/$15 (verify + bump
    # this entry on/after that date, or the spend gate under-reports the ~7x analyst fan-out).
    "claude-sonnet-5": (2.0, 10.0),
    "claude-sonnet-4-6": (3.0, 15.0),  # prior memo model; kept for the Phase 6 baseline record
    "claude-opus-4-8": (5.0, 25.0),
    # --- OpenRouter-form ids (Phase 14) ------------------------------------------------------------
    # Under LLM_PROVIDER=openrouter every id arrives PREFIXED ("anthropic/claude-sonnet-5") and, for
    # Opus, DOT-versioned ("4.8" not "4-8"). None of those matched the native keys above, so
    # is_known() was False and every OpenRouter call booked $0.00 — a silent zero, not an error.
    # Latent since the Phase 8 interlude; harmless while the paid Phase 12 eval ran on native
    # Anthropic ids, and caught 2026-07-20 when the phase-14 smoke test billed $0.87 against a
    # cost_summary() of $0.00. §12 makes cost_summary() the provenance source of record, so a silent
    # zero here would have left the whole benchmark with no cost data.
    # Prices pulled live from https://openrouter.ai/api/v1/models on 2026-07-20 and matching the
    # phase-14 §2.1 locked table to the cent. Re-pull before the core run.
    "anthropic/claude-haiku-4.5": (1.0, 5.0),
    "anthropic/claude-sonnet-5": (2.0, 10.0),  # same intro-pricing caveat as the native key above
    "anthropic/claude-opus-4.8": (5.0, 25.0),
    "anthropic/claude-fable-5": (10.0, 50.0),
    # Input corrected 5.0 -> 6.3 after the 2026-07-21 core run: the grounded-sol batch's actual
    # OpenRouter bill ran ~12% over cost_summary() at (5.0, 30.0), reconciling to ~$6.3/M input
    # (output ~$30/M held). cost_summary() is the §12 provenance record, so it must match the bill.
    "openai/gpt-5.6-sol": (6.3, 30.0),
    "google/gemini-3.5-flash": (1.5, 9.0),
    "google/gemini-3.1-pro-preview": (2.0, 12.0),
    "x-ai/grok-4.5": (2.0, 6.0),
    "deepseek/deepseek-v4-pro": (0.435, 0.87),
}

CACHE_READ_MULTIPLIER = 0.1  # cached-read input billed at ~0.1x the input rate
CACHE_WRITE_MULTIPLIER = 1.25  # 5-minute cache write at ~1.25x the input rate (verify at build)


def is_known(model: str) -> bool:
    # OpenRouter `:free` ids are $0 by definition and don't need per-model entries — the same reason
    # eval.run._is_free_run() lets them skip the spend gate.
    return model in RATES or model.endswith(":free")


def cost_usd(
    model: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> float:
    """Estimated USD for one call. An unknown model returns 0.0 (the caller flags `is_known`)."""
    in_rate, out_rate = RATES.get(model, (0.0, 0.0))
    return (
        input_tokens * in_rate
        + output_tokens * out_rate
        + cache_read_tokens * in_rate * CACHE_READ_MULTIPLIER
        + cache_write_tokens * in_rate * CACHE_WRITE_MULTIPLIER
    ) / 1_000_000
