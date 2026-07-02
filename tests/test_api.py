"""API tests — offline, StubLLM + stub retriever/laws, no API key, lifespan does not run."""

import json

import pytest
from fastapi.testclient import TestClient

from patchwork_assurance.api.main import (
    app,
    get_chat_llm,
    get_laws,
    get_memo_llm,
    get_retriever,
)
from patchwork_assurance.config import settings
from patchwork_assurance.core.contracts import ComplianceMemo
from patchwork_assurance.core.llm import LLMError, StubLLM

# ---- stub helpers ----


class _StubRetriever:
    def retrieve(self, query, filters=None, k=5):
        return []


MINIMAL_MEMO = ComplianceMemo(
    per_law=[],
    disclaimer="Educational analysis only — not legal advice.",
)

# ---- fixtures ----


@pytest.fixture(autouse=True)
def _reset_memo_rate_limit():
    # The per-IP memo counter is module-level and would otherwise accumulate across tests (same
    # TestClient IP, same process). Clear it before each test so single-call analyze tests don't 429.
    from patchwork_assurance.api.main import _memo_counts

    _memo_counts.clear()
    yield


@pytest.fixture
def analyze_client():
    app.dependency_overrides[get_retriever] = lambda: _StubRetriever()
    app.dependency_overrides[get_laws] = lambda: []
    app.dependency_overrides[get_memo_llm] = lambda: StubLLM(structured=MINIMAL_MEMO)
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def chat_client():
    app.dependency_overrides[get_retriever] = lambda: _StubRetriever()
    app.dependency_overrides[get_laws] = lambda: []
    app.dependency_overrides[get_chat_llm] = lambda: StubLLM(text="hello world")
    yield TestClient(app)
    app.dependency_overrides.clear()


# ---- helpers ----


def parse_sse(text: str) -> list[dict]:
    """Parse an SSE body into a list of {event, data} dicts."""
    events = []
    current: dict = {}
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("event:"):
            current["event"] = line[len("event:") :].strip()
        elif line.startswith("data:"):
            current["data"] = line[len("data:") :].strip()
        elif line == "" and current:
            events.append(current)
            current = {}
    if current:
        events.append(current)
    return events


# ---- /health ----


def test_health_reports_both_models():
    client = TestClient(app)
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["api"] == "ok"
    assert isinstance(body["core"]["corpus_size"], int)
    # Assert the endpoint echoes the configured models (whatever provider/.env is active) rather than
    # hardcoding Claude ids — so a local run on OpenRouter free models stays green too.
    assert body["chat_model"] == settings.chat_model
    assert body["memo_model"] == settings.memo_model


# ---- /meta ----


def test_meta_returns_corpus_vocab():
    from patchwork_assurance.core.corpus.metadata import LawMetadata

    law = LawMetadata.model_construct(
        jurisdiction="Colorado",
        regulated_roles=["deployer", "developer"],
        scope_domains=["employment", "financial_lending"],
    )
    app.dependency_overrides[get_laws] = lambda: [law]
    try:
        r = TestClient(app).get("/meta")
        assert r.status_code == 200
        body = r.json()
        assert body["jurisdictions"] == ["Colorado"]
        assert "employment" in body["decision_domains"]
        assert body["roles"] == ["deployer", "developer"]
    finally:
        app.dependency_overrides.clear()


# ---- /analyze ----

SITUATION = {
    "jurisdictions": ["Colorado"],
    "decision_domains": ["employment"],
    "roles": ["deployer"],
}


def test_analyze_happy_path(analyze_client):
    r = analyze_client.post("/analyze", json=SITUATION)
    assert r.status_code == 200
    body = r.json()
    assert "per_law" in body
    assert "disclaimer" in body
    assert body["disclaimer"] == MINIMAL_MEMO.disclaimer


def test_analyze_422_on_bad_domain(analyze_client):
    bad = {**SITUATION, "decision_domains": ["not_a_domain"]}
    r = analyze_client.post("/analyze", json=bad)
    assert r.status_code == 422
    assert "decision_domains" in r.text


def test_analyze_default_stub_is_valid_chrome_complete_memo():
    """The DEFAULT stub (what `make dev` uses with no key) must return a valid ComplianceMemo
    with the disclaimer present — invariant #4. Guards the partial-memo regression."""
    app.dependency_overrides[get_retriever] = lambda: _StubRetriever()
    app.dependency_overrides[get_laws] = lambda: []
    app.dependency_overrides[get_memo_llm] = lambda: StubLLM()  # no structured= → default path
    try:
        r = TestClient(app).post("/analyze", json=SITUATION)
        assert r.status_code == 200
        body = r.json()
        assert body["per_law"]  # non-empty
        assert body["disclaimer"]  # chrome present, not blank
    finally:
        app.dependency_overrides.clear()


class _RaisingLLM:
    """Simulates an upstream provider failure surfaced through core as LLMError."""

    def complete_structured(self, *a, **k):
        raise LLMError("simulated upstream failure")

    def complete(self, *a, **k):
        raise LLMError("simulated upstream failure")

    def stream(self, *a, **k):
        raise LLMError("simulated upstream failure")
        yield  # pragma: no cover — unreachable; makes this a generator


def test_analyze_llm_error_maps_to_502():
    app.dependency_overrides[get_retriever] = lambda: _StubRetriever()
    app.dependency_overrides[get_laws] = lambda: []
    app.dependency_overrides[get_memo_llm] = lambda: _RaisingLLM()
    try:
        r = TestClient(app).post("/analyze", json=SITUATION)
        assert r.status_code == 502
        assert "Upstream LLM error" in r.text
    finally:
        app.dependency_overrides.clear()


# ---- /analyze/stream SSE (Phase 12 observability) ----


def test_analyze_stream_single_pipeline_emits_memo_event(analyze_client):
    """The streaming twin of /analyze. In the default single pipeline there are no per-agent events,
    but the SSE still delivers the final ComplianceMemo as a 'memo' frame with the chrome intact."""
    r = analyze_client.post("/analyze/stream", json=SITUATION)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    events = parse_sse(r.text)
    memo_events = [e for e in events if e.get("event") == "memo"]
    assert len(memo_events) == 1
    body = json.loads(memo_events[0]["data"])
    assert "per_law" in body
    assert body["disclaimer"] == MINIMAL_MEMO.disclaimer


def test_analyze_stream_multi_agent_emits_agent_events_then_memo(monkeypatch):
    """With the multi_agent pipeline the on_event hook must reach the SSE: at least one analyst_start
    'agent' frame (naming the model), then the final memo. Fully offline on the bare StubLLM — the
    logged gotcha is that _generate_multi_agent builds the reviewer via build_llm(settings, ...), which
    reads llm_provider from .env, so pin it to 'stub' or it fires live OpenRouter calls."""
    from pathlib import Path

    from patchwork_assurance.core.scope import load_law_metadata

    monkeypatch.setattr(settings, "memo_pipeline", "multi_agent")
    monkeypatch.setattr(settings, "llm_provider", "stub")
    laws = load_law_metadata(Path(settings.corpus_path))
    app.dependency_overrides[get_retriever] = lambda: _StubRetriever()
    app.dependency_overrides[get_laws] = lambda: laws
    app.dependency_overrides[get_memo_llm] = lambda: StubLLM()  # analyst; reviewer built internally
    try:
        r = TestClient(app).post(
            "/analyze/stream",
            json={
                "jurisdictions": ["Colorado"],
                "decision_domains": ["employment"],
                "roles": ["deployer"],
            },
        )
        assert r.status_code == 200
        events = parse_sse(r.text)
        agent_events = [json.loads(e["data"]) for e in events if e.get("event") == "agent"]
        assert any(e["kind"] == "analyst_start" for e in agent_events)
        # The model id flows from config through the event so the panel can label it.
        starts = [e for e in agent_events if e["kind"] == "analyst_start"]
        assert all(e["model"] for e in starts)
        assert [e for e in events if e.get("event") == "memo"]
    finally:
        app.dependency_overrides.clear()


def test_analyze_stream_llm_error_emits_error_event(monkeypatch):
    """A provider failure mid-pipeline can't be an HTTP error code once streaming has started, so it
    surfaces as a terminal SSE 'error' frame (mirroring /chat)."""
    app.dependency_overrides[get_retriever] = lambda: _StubRetriever()
    app.dependency_overrides[get_laws] = lambda: []
    app.dependency_overrides[get_memo_llm] = lambda: _RaisingLLM()
    try:
        r = TestClient(app).post("/analyze/stream", json=SITUATION)
        assert r.status_code == 200  # stream opened before the failure
        events = parse_sse(r.text)
        error_events = [e for e in events if e.get("event") == "error"]
        assert error_events
        assert "Upstream LLM error" in json.loads(error_events[0]["data"])["detail"]
    finally:
        app.dependency_overrides.clear()


def test_analyze_stream_respects_rate_limit():
    """The Sonnet cost cap applies to the streaming path too (it rejects before the stream opens)."""
    app.dependency_overrides[get_retriever] = lambda: _StubRetriever()
    app.dependency_overrides[get_laws] = lambda: []
    app.dependency_overrides[get_memo_llm] = lambda: StubLLM(structured=MINIMAL_MEMO)
    try:
        client = TestClient(app)
        assert client.post("/analyze/stream", json=SITUATION).status_code == 200
        assert client.post("/analyze/stream", json=SITUATION).status_code == 200
        assert client.post("/analyze/stream", json=SITUATION).status_code == 429
    finally:
        app.dependency_overrides.clear()


# ---- memo rate limit ----


def test_memo_rate_limit_returns_429_after_limit():
    """The memo endpoint caps Sonnet cost at memo_daily_limit_per_ip (default 2) per IP; the
    (limit+1)th call from the same IP returns 429. (_reset_memo_rate_limit clears the counter first.)"""
    app.dependency_overrides[get_retriever] = lambda: _StubRetriever()
    app.dependency_overrides[get_laws] = lambda: []
    app.dependency_overrides[get_memo_llm] = lambda: StubLLM(structured=MINIMAL_MEMO)
    try:
        client = TestClient(app)
        assert client.post("/analyze", json=SITUATION).status_code == 200
        assert client.post("/analyze", json=SITUATION).status_code == 200
        r = client.post("/analyze", json=SITUATION)
        assert r.status_code == 429
        assert "limit" in r.text.lower()
    finally:
        app.dependency_overrides.clear()


def test_memo_quota_decrements_and_is_per_user():
    """/memo-quota reports remaining for the forwarded client IP, decrements after a memo, and is
    independent per IP (the per-user keying that X-Client-IP buys us)."""
    app.dependency_overrides[get_retriever] = lambda: _StubRetriever()
    app.dependency_overrides[get_laws] = lambda: []
    app.dependency_overrides[get_memo_llm] = lambda: StubLLM(structured=MINIMAL_MEMO)
    try:
        client = TestClient(app)
        a = {"X-Client-IP": "1.1.1.1"}
        b = {"X-Client-IP": "2.2.2.2"}
        assert client.get("/memo-quota", headers=a).json()["remaining"] == 2
        assert client.post("/analyze", json=SITUATION, headers=a).status_code == 200
        assert client.get("/memo-quota", headers=a).json()["remaining"] == 1  # user A used one
        assert client.get("/memo-quota", headers=b).json()["remaining"] == 2  # user B untouched
    finally:
        app.dependency_overrides.clear()


# ---- /chat SSE ----

MESSAGES = [{"role": "user", "content": "What must a Colorado deployer disclose?"}]


def test_chat_has_token_frames(chat_client):
    r = chat_client.post("/chat", json={"messages": MESSAGES})
    assert r.status_code == 200
    token_events = [e for e in parse_sse(r.text) if e.get("event") == "token"]
    assert len(token_events) > 0


def test_chat_has_terminal_sources_frame(chat_client):
    r = chat_client.post("/chat", json={"messages": MESSAGES})
    source_events = [e for e in parse_sse(r.text) if e.get("event") == "sources"]
    assert len(source_events) == 1
    payload = json.loads(source_events[0]["data"])
    assert "citations" in payload
    assert "disclaimer" in payload
    assert payload["disclaimer"]


def test_chat_sources_is_last_event(chat_client):
    r = chat_client.post("/chat", json={"messages": MESSAGES})
    named = [e for e in parse_sse(r.text) if "event" in e]
    assert named[-1]["event"] == "sources"
    assert all(e["event"] == "token" for e in named[:-1])


def test_chat_emits_terminal_error_event_on_llm_failure():
    """A mid-stream LLM failure can't be an HTTP error (200 already sent), so the stream must
    end with a terminal 'error' event and NOT a 'sources' event."""
    app.dependency_overrides[get_retriever] = lambda: _StubRetriever()
    app.dependency_overrides[get_laws] = lambda: []
    app.dependency_overrides[get_chat_llm] = lambda: _RaisingLLM()
    try:
        r = TestClient(app).post("/chat", json={"messages": MESSAGES})
        assert r.status_code == 200
        events = parse_sse(r.text)
        error_events = [e for e in events if e.get("event") == "error"]
        assert len(error_events) == 1
        assert "Upstream LLM error" in json.loads(error_events[0]["data"])["detail"]
        assert not any(e.get("event") == "sources" for e in events)
    finally:
        app.dependency_overrides.clear()
