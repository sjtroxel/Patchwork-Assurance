"""Observability tests — pricing, the Seam-4 usage/cost capture, request correlation, and the
privacy rule (logs never contain user content). Offline, no API calls."""

import logging

import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel

from patchwork_assurance.api.main import app
from patchwork_assurance.core import obs, pricing
from patchwork_assurance.core.contracts import Msg
from patchwork_assurance.core.llm import StubLLM


class _Capture(logging.Handler):
    """Captures records from the 'patchwork' logger and formats each line eagerly at emit time
    (so the request_id contextvar is read while it is still set)."""

    def __init__(self):
        super().__init__()
        self.records: list[logging.LogRecord] = []
        self.lines: list[str] = []
        self.setFormatter(obs.JSONFormatter())

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)
        self.lines.append(self.format(record))


@pytest.fixture
def cap():
    logger = logging.getLogger("patchwork")
    handler = _Capture()
    logger.addHandler(handler)
    try:
        yield handler
    finally:
        logger.removeHandler(handler)


class _Usage:
    input_tokens = 100
    output_tokens = 50
    cache_read_input_tokens = 0
    cache_creation_input_tokens = 0


class _Tiny(BaseModel):
    x: int = 0


# ---- pricing ----


def test_cost_usd_formula_and_unknown_model():
    # Sonnet: 1000 in @ $3/1M + 500 out @ $15/1M = 0.003 + 0.0075
    assert pricing.cost_usd("claude-sonnet-4-6", 1000, 500) == pytest.approx(0.0105)
    # cache read billed at 0.1x the input rate
    assert pricing.cost_usd(
        "claude-sonnet-4-6", 0, 0, cache_read_tokens=1_000_000
    ) == pytest.approx(0.3)
    # unknown model -> 0, and flagged
    assert pricing.cost_usd("mystery", 1000, 1000) == 0.0
    assert pricing.is_known("claude-haiku-4-5")
    assert not pricing.is_known("mystery")


# ---- usage/cost capture ----


def test_log_llm_call_records_metadata(cap):
    obs.log_llm_call("claude-haiku-4-5", _Usage(), 12.3, surface="complete")
    fields = cap.records[-1].fields
    assert fields["input_tokens"] == 100
    assert fields["output_tokens"] == 50
    assert fields["model"] == "claude-haiku-4-5"
    assert fields["surface"] == "complete"
    assert fields["est_cost_usd"] == pytest.approx((100 * 1 + 50 * 5) / 1e6)


def test_stub_llm_emits_zero_cost_trace(cap):
    StubLLM().complete("sys", [Msg(role="user", content="hi")])
    stub = next(r for r in cap.records if getattr(r, "fields", {}).get("model") == "stub")
    assert stub.fields["surface"] == "complete"
    assert stub.fields["est_cost_usd"] == 0.0


def test_cost_summary_accumulates(cap):
    before = obs.cost_summary()["llm_calls"]
    obs.log_llm_call("claude-haiku-4-5", _Usage(), 1.0, surface="complete")
    assert obs.cost_summary()["llm_calls"] == before + 1


# ---- privacy: logs NEVER contain user content ----


def test_logs_never_contain_user_content(cap):
    sentinel = "SECRET_SITUATION_DETAIL_xyz123"
    StubLLM(structured=_Tiny()).complete_structured(
        "system prompt", [Msg(role="user", content=sentinel)], schema=_Tiny
    )
    blob = "\n".join(cap.lines)
    assert "llm_call" in blob  # it did log the call
    assert sentinel not in blob  # but never the user's content


# ---- request correlation ----


def test_request_id_appears_in_log_line(cap):
    token = obs.set_request_id("req-xyz")
    try:
        obs.log_event("retrieve", k=8, n_results=3)
    finally:
        obs.reset_request_id(token)
    assert '"request_id": "req-xyz"' in cap.lines[-1]


def test_middleware_sets_and_echoes_request_id():
    client = TestClient(app)  # no lifespan: /health works offline
    generated = client.get("/health")
    assert generated.headers.get("x-request-id")
    echoed = client.get("/health", headers={"X-Request-ID": "fixed-id-123"})
    assert echoed.headers["x-request-id"] == "fixed-id-123"
