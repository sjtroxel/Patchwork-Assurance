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

import io
from dataclasses import dataclass
from typing import Literal

import httpx
import pypdf

from patchwork_assurance.config import SourceEntry
from patchwork_assurance.config import settings as _default_settings
from patchwork_assurance.core.agent.poll import REQUEST_HEADERS, PollResult, normalize_html
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

# Below this many extracted chars a PDF page set has no real text layer (a scanned image):
# pypdf returns ~nothing, so we fall through to OCR.
_PDF_MIN_TEXT_CHARS = 40
_OCR_DPI = 300  # render resolution for scanned-page OCR; statute scans read cleanly at 300
_OCR_MAX_PAGES = 60  # guard against a pathological multi-hundred-page scan blowing the cron budget


def _extract_pdf_textlayer(content: bytes) -> str:
    """Extract the embedded text layer via pypdf. Returns '' when there is none (scanned image)."""
    reader = pypdf.PdfReader(io.BytesIO(content))
    pages = [page.extract_text() or "" for page in reader.pages]
    return "\n".join(p.strip() for p in pages if p.strip()).strip()


def _ocr_pdf(content: bytes, url: str) -> str:
    """OCR a scanned (no-text-layer) PDF: render each page to an image, run tesseract.

    Imports are lazy so the app surfaces (memo/chat) never pay for them and so a runner
    missing the tesseract binary degrades to an honest note instead of crashing the cron.
    The OCR text is a *draft* — a human gates every agent PR before corpus entry, so OCR
    slips get caught at review (the human-in-the-loop boundary), not published blind.
    """
    try:
        import fitz  # PyMuPDF — renders pages without poppler (AGPL; swap to pypdfium2 to de-copyleft)
        import pytesseract
        from PIL import Image
    except Exception as exc:  # noqa: BLE001 — OCR deps absent: degrade, don't crash
        return (
            f"[PDF document at {url} appears to be a scanned image and OCR is unavailable "
            f"in this environment ({type(exc).__name__}). Manual review is required.]"
        )

    try:
        doc = fitz.open(stream=content, filetype="pdf")
        out: list[str] = []
        for page in doc[:_OCR_MAX_PAGES]:
            pix = page.get_pixmap(dpi=_OCR_DPI)
            img = Image.open(io.BytesIO(pix.tobytes("png")))
            out.append(pytesseract.image_to_string(img).strip())
        truncated = doc.page_count > _OCR_MAX_PAGES
        doc.close()
    except Exception as exc:  # noqa: BLE001 — render/OCR failure degrades to a note
        return (
            f"[PDF document at {url} could not be OCR'd ({type(exc).__name__}). "
            "Manual review is required.]"
        )

    text = "\n".join(p for p in out if p).strip()
    if len(text) < _PDF_MIN_TEXT_CHARS:
        return (
            f"[PDF document at {url} is a scanned image and OCR produced no readable text. "
            "Manual review is required.]"
        )
    if truncated:
        text += (
            f"\n\n[Truncated: only the first {_OCR_MAX_PAGES} pages were OCR'd; "
            "review the full source.]"
        )
    return text


def _extract_pdf_text(content: bytes, url: str) -> str:
    """Extract a PDF's text: embedded text layer first, OCR fallback for scanned images.

    Statute sources are bimodal — clean text-layer PDFs (extract instantly, no OCR cost) or
    scanned-image PDFs with no text layer (need OCR). Trying the text layer first means we
    only pay the OCR cost when there is genuinely no text to read.
    """
    try:
        textlayer = _extract_pdf_textlayer(content)
    except Exception as exc:  # noqa: BLE001 — malformed PDF: try OCR before giving up
        textlayer = ""
        if not content.startswith(b"%PDF"):
            return (
                f"[PDF document at {url} could not be parsed ({type(exc).__name__}). "
                "Manual review is required.]"
            )

    if len(textlayer) >= _PDF_MIN_TEXT_CHARS:
        return textlayer
    return _ocr_pdf(content, url)


def _extract_text(content: bytes, url: str, content_type: str) -> str:
    """Return human-readable text from an HTTP response. HTML is normalized; PDFs are extracted."""
    if "html" in content_type or url.endswith((".html", ".htm")):
        return normalize_html(content)
    if "pdf" in content_type or url.endswith(".pdf"):
        return _extract_pdf_text(content, url)
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
            resp = fetch(url, follow_redirects=True, timeout=30.0, headers=REQUEST_HEADERS)
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
