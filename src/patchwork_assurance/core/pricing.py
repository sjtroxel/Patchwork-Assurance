"""Per-token pricing in one place — rates churn, so this is the single spot to update
(Phase 7 IMPLEMENTATION §3).

Rates verified 2026-06-23 via the `claude-api` skill (cached 2026-06-04). Re-verify at build.

The four Anthropic `usage` fields are **additive**: total prompt tokens =
`input_tokens + cache_read_input_tokens + cache_creation_input_tokens`, where `input_tokens` is only the
UNCACHED remainder. So each tier is billed at its own rate below — never treat `input_tokens` as the whole
prompt (that under-bills a cached request and overstates the cache win).
"""

# model -> (input $/1M tokens, output $/1M tokens)
RATES: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5": (1.0, 5.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-opus-4-8": (5.0, 25.0),
}

CACHE_READ_MULTIPLIER = 0.1  # cached-read input billed at ~0.1x the input rate
CACHE_WRITE_MULTIPLIER = 1.25  # 5-minute cache write at ~1.25x the input rate (verify at build)


def is_known(model: str) -> bool:
    return model in RATES


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
