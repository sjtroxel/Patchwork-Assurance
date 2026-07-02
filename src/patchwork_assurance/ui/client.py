import json
from collections.abc import Iterator

import httpx

from patchwork_assurance.config import settings

# Fast paths (meta, quota) and the streamed chat are happy with a short read timeout.
TIMEOUT = httpx.Timeout(60.0, connect=10.0)
# /analyze is a single blocking call: deterministic scope + retrieval + a full non-streamed
# Sonnet memo. That can run well past 60s, so the memo path gets a generous read budget.
MEMO_TIMEOUT = httpx.Timeout(300.0, connect=10.0)


class APIError(Exception):
    """A clean, user-presentable failure. Pages render this as st.error, never a traceback."""


def _ip_headers(client_ip: str | None) -> dict[str, str]:
    # Forward the real browser IP so the memo rate limit keys per-user (the API otherwise sees only
    # the UI server). See api._client_ip. Best-effort cost control, not security.
    return {"X-Client-IP": client_ip} if client_ip else {}


def analyze(
    situation: dict, *, client: httpx.Client | None = None, client_ip: str | None = None
) -> dict:
    """POST /analyze. Returns the ComplianceMemo as a dict. Raises APIError on any failure."""
    send = client.post if client else httpx.post
    try:
        r = send(
            f"{settings.api_base_url}/analyze",
            json=situation,
            timeout=MEMO_TIMEOUT,
            headers=_ip_headers(client_ip),
        )
    except httpx.HTTPError as exc:
        raise APIError(f"Could not reach the analysis service at {settings.api_base_url}.") from exc
    if r.status_code == 422:
        raise APIError("That situation could not be processed. Please review the form inputs.")
    if r.status_code == 429:
        # Daily memo cap (Sonnet cost control); surface the server's friendly message.
        detail = (
            r.json().get("detail", "")
            if r.headers.get("content-type", "").startswith("application/json")
            else ""
        )
        raise APIError(detail or "You've reached today's memo limit. Chat is unlimited.")
    if r.status_code >= 500:
        raise APIError("The analysis service is temporarily unavailable. Please try again.")
    r.raise_for_status()
    return r.json()


def get_meta(*, client: httpx.Client | None = None) -> dict:
    """GET /meta. Returns the corpus-derived form vocab {jurisdictions, decision_domains, roles}.
    Raises APIError on any failure so the page can fall back / show a clean message."""
    send = client.get if client else httpx.get
    try:
        r = send(f"{settings.api_base_url}/meta", timeout=TIMEOUT)
    except httpx.HTTPError as exc:
        raise APIError(f"Could not reach the analysis service at {settings.api_base_url}.") from exc
    if r.status_code >= 500:
        raise APIError("The analysis service is temporarily unavailable. Please try again.")
    r.raise_for_status()
    return r.json()


def get_memo_quota(*, client: httpx.Client | None = None, client_ip: str | None = None) -> dict:
    """GET /memo-quota. Returns {limit, used, remaining} for the caller. Raises APIError on failure."""
    send = client.get if client else httpx.get
    try:
        r = send(
            f"{settings.api_base_url}/memo-quota",
            timeout=TIMEOUT,
            headers=_ip_headers(client_ip),
        )
    except httpx.HTTPError as exc:
        raise APIError(f"Could not reach the analysis service at {settings.api_base_url}.") from exc
    if r.status_code >= 500:
        raise APIError("The analysis service is temporarily unavailable. Please try again.")
    r.raise_for_status()
    return r.json()


def iter_sse_events(lines: Iterator[str]) -> Iterator[tuple[str, str]]:
    """Pure SSE parser. Yield (event, data) pairs from a line iterator.

    Handles: multi-line data: (rejoined with \\n), the default 'message' event when no event:
    line is present, and skips : comment lines (the API's 15s keep-alive pings).
    """
    event = "message"
    data: list[str] = []
    for raw in lines:
        line = raw.rstrip("\n")
        if line == "":
            if data:
                yield event, "\n".join(data)
            event, data = "message", []
            continue
        if line.startswith(":"):
            continue
        if line.startswith("event:"):
            event = line[len("event:") :].strip()
        elif line.startswith("data:"):
            raw = line[len("data:") :]
            data.append(raw[1:] if raw.startswith(" ") else raw)
    if data:
        yield event, "\n".join(data)


def stream_chat(
    messages: list[dict], *, client: httpx.Client | None = None
) -> Iterator[tuple[str, str]]:
    """POST /chat and yield (event, data) pairs: ('token', text), then ('sources', json)
    or ('error', json). Raises APIError if the connection fails before streaming starts."""
    _client = client or httpx.Client()
    _owned = client is None  # close only the client we created, never a caller-injected one
    try:
        with _client.stream(
            "POST",
            f"{settings.api_base_url}/chat",
            json={"messages": messages},
            timeout=TIMEOUT,
        ) as r:
            if r.status_code >= 500:
                raise APIError("The chat service is temporarily unavailable. Please try again.")
            r.raise_for_status()
            yield from iter_sse_events(r.iter_lines())
    except httpx.HTTPError as exc:
        raise APIError(f"Could not reach the chat service at {settings.api_base_url}.") from exc
    finally:
        if _owned:
            _client.close()


def analyze_stream(
    situation: dict,
    *,
    client: httpx.Client | None = None,
    client_ip: str | None = None,
) -> Iterator[tuple[str, str]]:
    """POST /analyze/stream and yield (event, data) pairs: ('agent', json) per pipeline step, then
    ('memo', json) with the final ComplianceMemo, or ('error', json). Raises APIError if the
    connection fails before streaming starts. Mirrors stream_chat; uses the long memo read budget
    (the multi-agent fan-out + reviewer runs well past 60s)."""
    _client = client or httpx.Client()
    _owned = client is None  # close only the client we created, never a caller-injected one
    try:
        with _client.stream(
            "POST",
            f"{settings.api_base_url}/analyze/stream",
            json=situation,
            timeout=MEMO_TIMEOUT,
            headers=_ip_headers(client_ip),
        ) as r:
            if r.status_code == 429:
                # The rate-limit dependency rejects BEFORE streaming starts, so this is a normal JSON
                # error body (not an SSE frame). Read it to surface the server's friendly message.
                try:
                    detail = json.loads(r.read()).get("detail", "")
                except Exception:
                    detail = ""
                raise APIError(detail or "You've reached today's memo limit. Chat is unlimited.")
            if r.status_code >= 500:
                raise APIError("The analysis service is temporarily unavailable. Please try again.")
            r.raise_for_status()
            yield from iter_sse_events(r.iter_lines())
    except httpx.HTTPError as exc:
        raise APIError(f"Could not reach the analysis service at {settings.api_base_url}.") from exc
    finally:
        if _owned:
            _client.close()


__all__ = [
    "APIError",
    "analyze",
    "analyze_stream",
    "get_memo_quota",
    "get_meta",
    "iter_sse_events",
    "stream_chat",
]
