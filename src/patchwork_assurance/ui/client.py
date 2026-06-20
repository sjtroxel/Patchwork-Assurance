from collections.abc import Iterator

import httpx

from patchwork_assurance.config import settings

TIMEOUT = httpx.Timeout(60.0, connect=10.0)


class APIError(Exception):
    """A clean, user-presentable failure. Pages render this as st.error, never a traceback."""


def analyze(situation: dict, *, client: httpx.Client | None = None) -> dict:
    """POST /analyze. Returns the ComplianceMemo as a dict. Raises APIError on any failure."""
    send = client.post if client else httpx.post
    try:
        r = send(f"{settings.api_base_url}/analyze", json=situation, timeout=TIMEOUT)
    except httpx.HTTPError as exc:
        raise APIError(f"Could not reach the analysis service at {settings.api_base_url}.") from exc
    if r.status_code == 422:
        raise APIError("That situation could not be processed. Please review the form inputs.")
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


__all__ = ["APIError", "analyze", "get_meta", "iter_sse_events", "stream_chat"]
