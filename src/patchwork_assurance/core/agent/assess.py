"""Assess + fetch stage (Phase 9 Batch 2).

Stage 3 of the five-stage monitoring pipeline: LLM-on-change only.
Only call this when PollResult.changed is True — the diff gate (Batch 1) is the
cost-control keystone; assess_change raises a ValueError if called on an unchanged source.

The Haiku LLM is given the source page and asked to:
  1. Call fetch_official_text(url) to read the full document.
  2. Call record_classification(verdict, reason) with its verdict.

The result carries the verdict + the fetched text, ready for the draft stage (Batch 3).

Public API:
    CLASSIFY_TOOLS          - Anthropic-shaped tool defs (also used to validate schema in tests)
    AssessResult            - dataclass returned by assess_change
    assess_change(...)      - runs the Haiku classify + fetch tool-use loop
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import httpx

from patchwork_assurance.config import SourceEntry
from patchwork_assurance.config import settings as _default_settings
from patchwork_assurance.core.agent.poll import PollResult, normalize_html
from patchwork_assurance.core.agent.provenance import is_allowed
from patchwork_assurance.core.contracts import Msg
from patchwork_assurance.core.llm import LLMClient

Verdict = Literal["relevant", "not_relevant", "uncertain"]

_CLASSIFY_SYSTEM = """\
You are a legal monitoring agent for Patchwork Assurance, an AI-regulation compliance tool.
Your task: assess whether a detected content change on a legislative source page represents a
relevant legal event — a new AI-regulation statute, an amendment, a repeal, or a court ruling
that interprets an AI law.

Steps:
1. Call `fetch_official_text` with the suggested URL to read the full document text.
2. Assess whether the change is a relevant AI-regulation legal event.
3. Call `record_classification` with your verdict: "relevant", "not_relevant", or "uncertain".

Be conservative: return "uncertain" rather than "not_relevant" if you cannot clearly determine
relevance. A human gate reviews every "relevant" and "uncertain" result before anything enters
the live corpus — never auto-publish.

Ground your verdict in the text you fetched. Do not fabricate or paraphrase statutory language."""

CLASSIFY_TOOLS = [
    {
        "name": "fetch_official_text",
        "description": (
            "Fetch the full text of an official legislative document. "
            "Call this before classifying so your verdict is grounded in the actual text."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL of the official document to fetch.",
                }
            },
            "required": ["url"],
        },
    },
    {
        "name": "record_classification",
        "description": "Record your final classification verdict after reviewing the document.",
        "input_schema": {
            "type": "object",
            "properties": {
                "verdict": {
                    "type": "string",
                    "enum": ["relevant", "not_relevant", "uncertain"],
                    "description": "Whether this change is a relevant AI-regulation legal event.",
                },
                "reason": {
                    "type": "string",
                    "description": "Brief reason for the verdict (1-2 sentences).",
                },
            },
            "required": ["verdict", "reason"],
        },
    },
]

_VALID_VERDICTS = frozenset({"relevant", "not_relevant", "uncertain"})
_TEXT_CAP = 8000  # chars fed back to the model per fetch (keeps context manageable)


def _extract_text(content: bytes, url: str, content_type: str) -> str:
    """Return human-readable text from an HTTP response. HTML is normalized; PDFs are noted."""
    if "html" in content_type or url.endswith((".html", ".htm")):
        return normalize_html(content)
    if "pdf" in content_type or url.endswith(".pdf"):
        return (
            f"[PDF document at {url}. Automated text extraction is not supported; "
            "manual review or a dedicated PDF step is required.]"
        )
    return content.decode("utf-8", errors="replace")


@dataclass
class AssessResult:
    source: SourceEntry
    verdict: Verdict
    reason: str
    official_text: str | None = None  # the fetched document text (populated when fetch was called)
    official_url_fetched: str | None = None


def assess_change(
    poll_result: PollResult,
    llm: LLMClient,
    *,
    http_client: httpx.Client | None = None,
    allowed_source_domains: list[str] | None = None,
) -> AssessResult:
    """Classify relevance and optionally fetch the official text for one changed source.

    The LLM (Haiku) is invoked via run_tools: it calls fetch_official_text then
    record_classification. If the loop ends without record_classification, verdict
    defaults to "uncertain" (the safe, human-gated fallback).

    Provenance: fetch_official_text only fetches URLs on the provenance allowlist. A page
    altered to redirect the agent at a non-official source (indirect injection) is refused
    before any network call — the agent ingests official text only (plan §8). Defaults to
    settings.allowed_source_domains.

    Raises:
        ValueError: if poll_result.changed is False (caller bug; the diff gate prevents this).
    """
    if not poll_result.changed:
        raise ValueError(
            f"assess_change called on unchanged source {poll_result.source.url!r}. "
            "The diff gate (poll_source / poll_all) should prevent this call."
        )

    allowed = (
        allowed_source_domains
        if allowed_source_domains is not None
        else _default_settings.allowed_source_domains
    )
    source = poll_result.source
    state: dict = {"verdict": "uncertain", "reason": "", "text": None, "url": None}

    def dispatch(name: str, args: dict) -> str:
        if name == "fetch_official_text":
            url = args.get("url") or source.official_url or source.url
            if not is_allowed(url, allowed):
                # Provenance gate: refuse to fetch a non-official source (no network call).
                return (
                    f"Refused: {url} is not on the official-source allowlist. "
                    "Fetch only from allowlisted official legislative/court sources."
                )
            fetch = http_client.get if http_client else httpx.get
            resp = fetch(url, follow_redirects=True, timeout=30.0)
            resp.raise_for_status()
            content_type = getattr(resp, "headers", {}).get("content-type", "")
            text = _extract_text(resp.content, url, content_type)
            state["text"] = text
            state["url"] = url
            return text[:_TEXT_CAP]

        if name == "record_classification":
            v = args.get("verdict", "uncertain")
            state["verdict"] = v if v in _VALID_VERDICTS else "uncertain"
            state["reason"] = args.get("reason", "")
            return "Classification recorded."

        return f"Unknown tool: {name}"

    hint_url = source.official_url or source.url
    user_msg = (
        f"A content change was detected on the legislative source page for "
        f"**{source.jurisdiction.upper()}** ({source.url}).\n\n"
        f"Suggested fetch target: {hint_url}\n\n"
        "Please fetch the official text, assess relevance, and record your classification."
    )

    llm.run_tools(
        _CLASSIFY_SYSTEM,
        [Msg(role="user", content=user_msg)],
        CLASSIFY_TOOLS,
        dispatch,
    )

    verdict: Verdict = state["verdict"]  # type: ignore[assignment]
    return AssessResult(
        source=source,
        verdict=verdict,
        reason=state["reason"],
        official_text=state["text"],
        official_url_fetched=state["url"],
    )
