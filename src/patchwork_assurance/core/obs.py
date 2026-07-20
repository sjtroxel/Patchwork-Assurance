"""Observability — structured JSON logging + request correlation + LLM cost capture (Phase 7).

Stdlib `logging` only (no new dependency, in keeping with the project's no-framework ethos).

**HARD RULE — metadata only.** Every log line records `request_id`, `stage`/`event`, latency, token
counts, cost, and model. It NEVER records the user's situation text, chat messages, retrieved chunk
text, or generated output (the privacy invariant — "we don't store your inputs", ROADMAP §8). The
helpers below accept only metadata; do not pass request/response content into `fields`.
"""

import json
import logging
import sys
import time
from contextvars import ContextVar

from patchwork_assurance.config import settings
from patchwork_assurance.core import pricing

# request_id is threaded via a ContextVar so core/ functions never grow a request_id parameter.
# NOTE (verify at build): the API runs LLM calls in a threadpool (run_in_threadpool /
# iterate_in_threadpool); anyio copies the context into the worker thread, so this propagates — confirm
# a real Seam-4 log line carries the request_id during the live deploy.
_request_id: ContextVar[str] = ContextVar("request_id", default="")

# In-memory, per-process rolling totals (counts/sums only; resets on restart — stateless invariant).
_totals: dict[str, float] = {
    "llm_calls": 0,
    "cost_usd": 0.0,
    "input_tokens": 0,
    "output_tokens": 0,
    # Calls whose model is absent from pricing.RATES. Their cost books as 0.0, so without this
    # counter a fully-unpriced run is indistinguishable from a free one — exactly the 2026-07-20
    # failure, where the phase-14 smoke billed $0.87 against a cost_summary() reading $0.00.
    # cost_usd is a FLOOR whenever this is nonzero; §12 makes cost_summary() the provenance record.
    "unknown_rate_calls": 0,
}


class JSONFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "event": record.getMessage(),
            "request_id": _request_id.get(),
        }
        fields = getattr(record, "fields", None)
        if fields:
            payload.update(fields)
        return json.dumps(payload, default=str)


def _build_logger() -> logging.Logger:
    logger = logging.getLogger("patchwork")
    logger.setLevel(settings.log_level.upper())
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.propagate = False  # don't double-log via the root logger
    return logger


_logger = _build_logger()


# ---- request correlation ----
def set_request_id(rid: str):
    """Set the current request id; returns a token to pass to reset_request_id."""
    return _request_id.set(rid)


def reset_request_id(token) -> None:
    _request_id.reset(token)


def get_request_id() -> str:
    return _request_id.get()


# ---- events ----
def log_event(event: str, **fields) -> None:
    """Emit one structured, metadata-only log line. Never pass user/model content in fields."""
    if not settings.enable_tracing:
        return
    _logger.info(event, extra={"fields": fields})


def _usage_field(usage, name: str) -> int:
    if usage is None:
        return 0
    return int(getattr(usage, name, 0) or 0)


def log_llm_call(model: str, usage, latency_ms: float, *, surface: str) -> None:
    """Record one LLM call: model, the four token fields, latency, estimated cost. `usage` may be a
    provider usage object or None (e.g. an interrupted/failed stream). Metadata only — no content."""
    input_tokens = _usage_field(usage, "input_tokens")
    output_tokens = _usage_field(usage, "output_tokens")
    cache_read = _usage_field(usage, "cache_read_input_tokens")
    cache_write = _usage_field(usage, "cache_creation_input_tokens")
    cost = pricing.cost_usd(model, input_tokens, output_tokens, cache_read, cache_write)
    known = pricing.is_known(model)

    _totals["llm_calls"] += 1
    _totals["cost_usd"] += cost
    _totals["input_tokens"] += input_tokens
    _totals["output_tokens"] += output_tokens
    if not known:
        _totals["unknown_rate_calls"] += 1

    log_event(
        "llm_call",
        surface=surface,
        model=model,
        known_rate=known,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read,
        cache_write_tokens=cache_write,
        latency_ms=round(latency_ms, 1),
        est_cost_usd=round(cost, 6),
    )


def cost_summary() -> dict:
    """Per-process rolling totals (resets on restart). Metadata only."""
    return dict(_totals)


def now_ms() -> float:
    """Monotonic millisecond clock for stage timing."""
    return time.perf_counter() * 1000
