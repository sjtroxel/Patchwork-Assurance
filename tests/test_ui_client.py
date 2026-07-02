"""Unit tests for ui/client.py — fully offline via httpx.MockTransport."""

import json

import httpx
import pytest

from patchwork_assurance.ui.client import (
    APIError,
    analyze,
    analyze_stream,
    get_memo_quota,
    get_meta,
    iter_sse_events,
    stream_chat,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_MEMO = {
    "per_law": [
        {
            "law_id": "co-sb26-189",
            "short_name": "CO SB 26-189",
            "in_scope": "yes",
            "why": "Deployer of an ADMT that materially influences employment decisions.",
            "obligations": [{"text": "Provide notice.", "citation": "Colorado § 6-1-1704"}],
            "effective_dates": ["2027-01-01"],
        }
    ],
    "draft_notices": [],
    "deadline_checklist": [
        {"date": "2027-01-01", "what": "Compliance deadline", "law": "CO SB 26-189"}
    ],
    "disclaimer": "Educational analysis, not legal advice.",
}

SAMPLE_SITUATION = {
    "jurisdictions": ["Colorado"],
    "decision_domains": ["employment"],
    "roles": ["deployer"],
    "ai_use": "yes",
    "notes": "",
}


def _mock_client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler))


# ---------------------------------------------------------------------------
# analyze()
# ---------------------------------------------------------------------------


def test_analyze_happy_path():
    def handler(request):
        return httpx.Response(200, json=SAMPLE_MEMO)

    result = analyze(SAMPLE_SITUATION, client=_mock_client(handler))
    assert "per_law" in result
    assert result["disclaimer"] == "Educational analysis, not legal advice."


def test_analyze_422_raises_api_error():
    def handler(request):
        return httpx.Response(422, json={"detail": "validation error"})

    with pytest.raises(APIError, match="could not be processed"):
        analyze(SAMPLE_SITUATION, client=_mock_client(handler))


def test_analyze_500_raises_api_error():
    def handler(request):
        return httpx.Response(503, json={"detail": "service unavailable"})

    with pytest.raises(APIError, match="temporarily unavailable"):
        analyze(SAMPLE_SITUATION, client=_mock_client(handler))


def test_analyze_429_surfaces_rate_limit_message():
    def handler(request):
        return httpx.Response(
            429, json={"detail": "You've reached today's limit of 2 compliance memos."}
        )

    with pytest.raises(APIError, match="today's limit"):
        analyze(SAMPLE_SITUATION, client=_mock_client(handler))


def test_analyze_forwards_client_ip_header():
    def handler(request):
        assert request.headers.get("x-client-ip") == "203.0.113.7"
        return httpx.Response(200, json=SAMPLE_MEMO)

    analyze(SAMPLE_SITUATION, client=_mock_client(handler), client_ip="203.0.113.7")


def test_get_memo_quota_returns_dict_and_forwards_ip():
    def handler(request):
        assert request.headers.get("x-client-ip") == "203.0.113.7"
        return httpx.Response(200, json={"limit": 2, "used": 1, "remaining": 1})

    result = get_memo_quota(client=_mock_client(handler), client_ip="203.0.113.7")
    assert result == {"limit": 2, "used": 1, "remaining": 1}


def test_analyze_connection_error_raises_api_error():
    def handler(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(APIError, match="Could not reach"):
        analyze(SAMPLE_SITUATION, client=_mock_client(handler))


# ---------------------------------------------------------------------------
# get_meta()
# ---------------------------------------------------------------------------


def test_get_meta_happy_path():
    def handler(request):
        return httpx.Response(
            200,
            json={
                "jurisdictions": ["Colorado", "Connecticut"],
                "decision_domains": ["employment"],
                "roles": ["deployer", "developer"],
            },
        )

    result = get_meta(client=_mock_client(handler))
    assert result["jurisdictions"] == ["Colorado", "Connecticut"]
    assert "employment" in result["decision_domains"]


def test_get_meta_500_raises_api_error():
    def handler(request):
        return httpx.Response(503)

    with pytest.raises(APIError, match="temporarily unavailable"):
        get_meta(client=_mock_client(handler))


# ---------------------------------------------------------------------------
# iter_sse_events() — the high-value pure-function test
# ---------------------------------------------------------------------------


def test_iter_sse_events_basic_sequence():
    lines = [
        "event: token\n",
        "data: Hello\n",
        "\n",
        "event: token\n",
        "data: World\n",
        "\n",
        "event: sources\n",
        'data: {"citations": ["CO § 6-1-1704"], "disclaimer": "Not legal advice."}\n',
        "\n",
    ]
    events = list(iter_sse_events(iter(lines)))
    assert events == [
        ("token", "Hello"),
        ("token", "World"),
        ("sources", '{"citations": ["CO § 6-1-1704"], "disclaimer": "Not legal advice."}'),
    ]


def test_iter_sse_events_skips_ping_comments():
    lines = [
        "event: token\n",
        "data: First\n",
        "\n",
        ": ping - 2026-06-19T09:00:00Z\n",
        "event: token\n",
        "data: Second\n",
        "\n",
        "event: sources\n",
        'data: {"citations": []}\n',
        "\n",
    ]
    events = list(iter_sse_events(iter(lines)))
    assert len(events) == 3
    assert events[0] == ("token", "First")
    assert events[1] == ("token", "Second")
    assert events[2][0] == "sources"


def test_iter_sse_events_multiline_data_rejoined():
    lines = [
        "event: token\n",
        "data: line one\n",
        "data: line two\n",
        "\n",
    ]
    events = list(iter_sse_events(iter(lines)))
    assert events == [("token", "line one\nline two")]


def test_iter_sse_events_error_terminal():
    lines = [
        "event: error\n",
        'data: {"detail": "LLM failed"}\n',
        "\n",
    ]
    events = list(iter_sse_events(iter(lines)))
    assert events == [("error", '{"detail": "LLM failed"}')]


def test_iter_sse_events_flush_without_trailing_blank():
    """A stream that ends without a final blank line still yields the last event."""
    lines = [
        "event: token\n",
        "data: Final\n",
        # no trailing blank line
    ]
    events = list(iter_sse_events(iter(lines)))
    assert events == [("token", "Final")]


# ---------------------------------------------------------------------------
# stream_chat()
# ---------------------------------------------------------------------------


def _sse_body(*events: tuple[str, str]) -> bytes:
    """Build a minimal SSE byte body from (event, data) pairs."""
    parts = []
    for ev, data in events:
        parts.append(f"event: {ev}\ndata: {data}\n\n")
    return "".join(parts).encode()


def test_stream_chat_yields_token_then_sources():
    sources_payload = json.dumps(
        {"citations": ["CO § 6-1-1704"], "disclaimer": "Not legal advice."}
    )
    body = _sse_body(("token", "Hello"), ("token", " world"), ("sources", sources_payload))

    def handler(request):
        return httpx.Response(200, content=body)

    events = list(stream_chat([{"role": "user", "content": "Hi"}], client=_mock_client(handler)))
    assert events[0] == ("token", "Hello")
    assert events[1] == ("token", " world")
    assert events[2][0] == "sources"
    parsed = json.loads(events[2][1])
    assert parsed["citations"] == ["CO § 6-1-1704"]


def test_stream_chat_500_raises_api_error():
    def handler(request):
        return httpx.Response(503)

    with pytest.raises(APIError, match="temporarily unavailable"):
        list(stream_chat([{"role": "user", "content": "Hi"}], client=_mock_client(handler)))


def test_stream_chat_connection_error_raises_api_error():
    def handler(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(APIError, match="Could not reach"):
        list(stream_chat([{"role": "user", "content": "Hi"}], client=_mock_client(handler)))


# ---------------------------------------------------------------------------
# analyze_stream() — the Phase 12 observability SSE (agent events, then memo)
# ---------------------------------------------------------------------------


def test_analyze_stream_yields_agent_events_then_memo():
    agent = json.dumps(
        {"kind": "analyst_start", "model": "claude-sonnet-5", "law_id": "co", "detail": "CO SB"}
    )
    body = _sse_body(("agent", agent), ("memo", json.dumps(SAMPLE_MEMO)))

    def handler(request):
        assert request.url.path == "/analyze/stream"
        return httpx.Response(200, content=body)

    events = list(analyze_stream(SAMPLE_SITUATION, client=_mock_client(handler)))
    assert events[0][0] == "agent"
    assert json.loads(events[0][1])["model"] == "claude-sonnet-5"
    assert events[1][0] == "memo"
    assert json.loads(events[1][1])["per_law"][0]["law_id"] == "co-sb26-189"


def test_analyze_stream_forwards_client_ip_header():
    def handler(request):
        assert request.headers.get("x-client-ip") == "203.0.113.7"
        return httpx.Response(200, content=_sse_body(("memo", json.dumps(SAMPLE_MEMO))))

    list(analyze_stream(SAMPLE_SITUATION, client=_mock_client(handler), client_ip="203.0.113.7"))


def test_analyze_stream_429_surfaces_rate_limit_message():
    def handler(request):
        return httpx.Response(429, json={"detail": "You've reached today's limit of 2 memos."})

    with pytest.raises(APIError, match="today's limit"):
        list(analyze_stream(SAMPLE_SITUATION, client=_mock_client(handler)))


def test_analyze_stream_500_raises_api_error():
    def handler(request):
        return httpx.Response(503)

    with pytest.raises(APIError, match="temporarily unavailable"):
        list(analyze_stream(SAMPLE_SITUATION, client=_mock_client(handler)))


def test_analyze_stream_connection_error_raises_api_error():
    def handler(request):
        raise httpx.ConnectError("refused")

    with pytest.raises(APIError, match="Could not reach"):
        list(analyze_stream(SAMPLE_SITUATION, client=_mock_client(handler)))
