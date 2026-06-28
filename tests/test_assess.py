"""Phase 9 Batch 2 — assess + fetch (offline only; StubLLM tool_script, no network, no tokens).

Key assertions:
- assess_change raises ValueError on an unchanged source (cost-control keystone)
- StubLLM tool_script drives the real dispatch (fetch + record_classification)
- AssessResult carries the verdict, reason, and fetched official text
- "uncertain" is the safe default when the LLM never calls record_classification
- CLASSIFY_TOOLS has the correct Anthropic tool shape
"""

import io

import pytest

from patchwork_assurance.config import SourceEntry
from patchwork_assurance.core.agent.assess import CLASSIFY_TOOLS, AssessResult, assess_change
from patchwork_assurance.core.agent.poll import PollResult
from patchwork_assurance.core.llm import StubLLM

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

_HTML = b"""
<html><body>
<nav>Menu ignored</nav>
<main>
  <h1>Illinois HB 3773 \xe2\x80\x94 Public Act 103-0804</h1>
  <p>Status: Enacted, effective January 1, 2026.</p>
  <p>An AI system used in employment decisions that results in discrimination
  violates the Illinois Human Rights Act.</p>
</main>
</body></html>
"""

_SOURCE = SourceEntry(
    jurisdiction="il",
    url="https://www.ilga.gov/Legislation/publicacts/view/103-0804",
    official_url="https://www.ilga.gov/documents/legislation/publicacts/103/103-0804.htm",
    kind="html",
)

_CHANGED = PollResult(source=_SOURCE, changed=True, new_hash="newhash")
_UNCHANGED = PollResult(source=_SOURCE, changed=False, new_hash="samehash")


class _FakeResponse:
    def __init__(self, content: bytes, content_type: str = "text/html; charset=utf-8") -> None:
        self.content = content
        self.headers = {"content-type": content_type}

    def raise_for_status(self) -> None:
        pass


class _FakeClient:
    def __init__(self, responses: dict[str, bytes]) -> None:
        self._responses = responses

    def get(self, url: str, **kwargs) -> _FakeResponse:
        return _FakeResponse(self._responses[url])


def _client() -> _FakeClient:
    return _FakeClient({_SOURCE.official_url: _HTML})


# ---------------------------------------------------------------------------
# Diff-gate enforcement
# ---------------------------------------------------------------------------


def test_assess_change_raises_on_unchanged_source():
    with pytest.raises(ValueError, match="unchanged source"):
        assess_change(_UNCHANGED, StubLLM())


# ---------------------------------------------------------------------------
# Relevant verdict — the happy path
# ---------------------------------------------------------------------------


def test_assess_change_relevant_verdict():
    llm = StubLLM(
        text="New IL employment AI law — relevant.",
        tool_script=[
            ("fetch_official_text", {"url": _SOURCE.official_url}),
            (
                "record_classification",
                {"verdict": "relevant", "reason": "New IL AI employment statute."},
            ),
        ],
    )

    result = assess_change(_CHANGED, llm, http_client=_client())

    assert isinstance(result, AssessResult)
    assert result.verdict == "relevant"
    assert result.reason == "New IL AI employment statute."
    assert result.source == _SOURCE


def test_assess_change_populates_official_text_when_fetched():
    llm = StubLLM(
        text="Relevant.",
        tool_script=[
            ("fetch_official_text", {"url": _SOURCE.official_url}),
            ("record_classification", {"verdict": "relevant", "reason": "IL AI law."}),
        ],
    )

    result = assess_change(_CHANGED, llm, http_client=_client())

    assert result.official_text is not None
    assert "employment" in result.official_text.lower()
    assert result.official_url_fetched == _SOURCE.official_url


# ---------------------------------------------------------------------------
# Not-relevant verdict
# ---------------------------------------------------------------------------


def test_assess_change_not_relevant_verdict():
    llm = StubLLM(
        text="Not relevant.",
        tool_script=[
            ("fetch_official_text", {"url": _SOURCE.official_url}),
            (
                "record_classification",
                {"verdict": "not_relevant", "reason": "Minor nav update only."},
            ),
        ],
    )

    result = assess_change(_CHANGED, llm, http_client=_client())

    assert result.verdict == "not_relevant"
    assert result.reason == "Minor nav update only."


# ---------------------------------------------------------------------------
# Uncertain default when record_classification is never called
# ---------------------------------------------------------------------------


def test_assess_change_defaults_to_uncertain_when_no_classification_recorded():
    llm = StubLLM(
        text="Cannot determine.",
        tool_script=[
            ("fetch_official_text", {"url": _SOURCE.official_url}),
            # record_classification intentionally omitted
        ],
    )

    result = assess_change(_CHANGED, llm, http_client=_client())

    assert result.verdict == "uncertain"
    assert result.reason == ""  # no reason recorded


# ---------------------------------------------------------------------------
# Uncertain default when only record_classification is called (no fetch)
# ---------------------------------------------------------------------------


def test_assess_change_no_fetch_no_official_text():
    llm = StubLLM(
        text="Classified without fetching.",
        tool_script=[
            (
                "record_classification",
                {"verdict": "uncertain", "reason": "Could not access document."},
            ),
        ],
    )

    result = assess_change(_CHANGED, llm, http_client=_client())

    assert result.verdict == "uncertain"
    assert result.official_text is None
    assert result.official_url_fetched is None


# ---------------------------------------------------------------------------
# Invalid verdict from model → normalised to "uncertain"
# ---------------------------------------------------------------------------


def test_assess_change_invalid_verdict_normalised_to_uncertain():
    llm = StubLLM(
        text="Done.",
        tool_script=[
            ("record_classification", {"verdict": "maybe", "reason": "Unclear."}),
        ],
    )

    result = assess_change(_CHANGED, llm, http_client=_client())

    assert result.verdict == "uncertain"


# ---------------------------------------------------------------------------
# PDF extraction: real text layer, scanned-image fallback, malformed fallback
# ---------------------------------------------------------------------------


def _make_pdf(text: str) -> bytes:
    """Build a minimal single-page text-layer PDF showing `text` (no external deps)."""
    objs = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
    ]
    stream = b"BT /F1 24 Tf 72 700 Td (" + text.encode() + b") Tj ET"
    objs.append(
        b"<< /Length " + str(len(stream)).encode() + b" >>\nstream\n" + stream + b"\nendstream"
    )
    objs.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objs, start=1):
        offsets.append(out.tell())
        out.write(str(i).encode() + b" 0 obj\n" + body + b"\nendobj\n")
    xref_pos = out.tell()
    out.write(b"xref\n0 " + str(len(objs) + 1).encode() + b"\n")
    out.write(b"0000000000 65535 f \n")
    for off in offsets:
        out.write(f"{off:010d} 00000 n \n".encode())
    out.write(
        b"trailer\n<< /Size " + str(len(objs) + 1).encode() + b" /Root 1 0 R >>\n"
        b"startxref\n" + str(xref_pos).encode() + b"\n%%EOF"
    )
    return out.getvalue()


_PDF_SOURCE = SourceEntry(
    jurisdiction="co",
    url="https://leg.colorado.gov/bills/sb26-189",
    official_url="https://leg.colorado.gov/bill_files/116489/download",
    kind="pdf",
)


def _pdf_assess(content: bytes) -> AssessResult:
    pdf_changed = PollResult(source=_PDF_SOURCE, changed=True, new_hash="x")

    class _PdfClient:
        def get(self, url: str, **kwargs) -> _FakeResponse:
            return _FakeResponse(content, content_type="application/pdf")

    llm = StubLLM(
        text="Reviewed PDF.",
        tool_script=[
            ("fetch_official_text", {"url": _PDF_SOURCE.official_url}),
            ("record_classification", {"verdict": "relevant", "reason": "AI statute amendment."}),
        ],
    )
    return assess_change(pdf_changed, llm, http_client=_PdfClient())


def _ocr_available() -> bool:
    """True only when the full OCR stack (renderer + tesseract binary) is usable."""
    try:
        import fitz  # noqa: F401
        import pytesseract
        from PIL import Image  # noqa: F401

        pytesseract.get_tesseract_version()
        return True
    except Exception:
        return False


def _make_scanned_pdf(text: str) -> bytes:
    """Build a PDF with NO text layer — text rasterized into a full-page image (the scan case)."""
    import fitz
    from PIL import Image, ImageDraw, ImageFont

    img = Image.new("RGB", (1400, 300), "white")
    draw = ImageDraw.Draw(img)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36)
    except OSError:
        font = ImageFont.load_default()
    draw.text((30, 120), text, fill="black", font=font)
    buf = io.BytesIO()
    img.save(buf, format="PNG")

    doc = fitz.open()
    page = doc.new_page(width=1400, height=300)
    page.insert_image(fitz.Rect(0, 0, 1400, 300), stream=buf.getvalue())
    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes


def test_assess_change_pdf_extracts_text_layer():
    # Text-layer PDFs extract directly — the fast path, no OCR cost.
    result = _pdf_assess(_make_pdf("Colorado SB 26-189 amendment effective 2026"))

    assert result.official_text is not None
    assert "Colorado SB 26-189 amendment effective 2026" in result.official_text
    assert result.verdict == "relevant"


@pytest.mark.skipif(not _ocr_available(), reason="tesseract OCR stack not installed")
def test_assess_change_pdf_scanned_image_is_ocred():
    # The worst case: a scanned-image PDF with no text layer. pypdf yields nothing, so the
    # OCR fallback renders the page and reads the text back. (String >40 chars to clear the
    # min-real-text floor, as a genuine statute page always would.)
    statute = "Connecticut Senate Bill 5 governs automated employment decision tools."
    result = _pdf_assess(_make_scanned_pdf(statute))

    assert result.official_text is not None
    assert "Connecticut" in result.official_text
    assert "automated" in result.official_text


def test_assess_change_pdf_malformed_returns_note():
    # Bytes that are not a PDF at all (a fetch that returned the wrong content) degrade to a
    # clear note rather than crashing the pipeline.
    result = _pdf_assess(b"this is not a pdf at all")

    assert result.official_text is not None
    assert "could not be parsed" in result.official_text


def test_assess_fetch_sends_browser_user_agent():
    # The assess-stage fetch must carry the same browser UA as poll, or sources that 403 a
    # default python UA (e.g. nj.gov) detect-as-changed but then fail to fetch the text.
    captured: dict = {}

    class _CapturingClient:
        def get(self, url: str, **kwargs) -> _FakeResponse:
            captured.update(kwargs)
            return _FakeResponse(_HTML)

    llm = StubLLM(
        text="Reviewed.",
        tool_script=[
            ("fetch_official_text", {"url": _SOURCE.official_url}),
            ("record_classification", {"verdict": "relevant", "reason": "ok"}),
        ],
    )
    assess_change(_CHANGED, llm, http_client=_CapturingClient())

    assert "User-Agent" in captured["headers"]
    assert "Mozilla" in captured["headers"]["User-Agent"]


# ---------------------------------------------------------------------------
# Provenance: fetch refuses a non-allowlisted URL (indirect-injection redirect)
# ---------------------------------------------------------------------------


def test_assess_change_refuses_non_allowlisted_fetch_url():
    # Simulates a poisoned source page that redirects the agent to fetch from an
    # attacker domain. The fetch is refused before any network call; no official_text
    # is captured, so the draft stage has nothing to work from.
    evil_url = "https://evil.example.com/fake-statute.html"

    class _ShouldNotFetchClient:
        def get(self, url: str, **kwargs) -> _FakeResponse:
            raise AssertionError(f"fetch must be refused, but it tried to GET {url}")

    llm = StubLLM(
        text="Tried to fetch attacker URL.",
        tool_script=[
            ("fetch_official_text", {"url": evil_url}),
            ("record_classification", {"verdict": "relevant", "reason": "Injected redirect."}),
        ],
    )

    result = assess_change(
        _CHANGED,
        llm,
        http_client=_ShouldNotFetchClient(),
        allowed_source_domains=["ilga.gov"],
    )

    # The model's verdict is still recorded, but no text was fetched from the evil URL.
    assert result.official_text is None
    assert result.official_url_fetched is None


def test_assess_change_allows_allowlisted_fetch_url():
    llm = StubLLM(
        text="Fetched official source.",
        tool_script=[
            ("fetch_official_text", {"url": _SOURCE.official_url}),
            ("record_classification", {"verdict": "relevant", "reason": "Official IL source."}),
        ],
    )

    result = assess_change(
        _CHANGED,
        llm,
        http_client=_client(),
        allowed_source_domains=["ilga.gov"],
    )

    assert result.official_text is not None
    assert result.official_url_fetched == _SOURCE.official_url


# ---------------------------------------------------------------------------
# CLASSIFY_TOOLS shape (Anthropic tool schema)
# ---------------------------------------------------------------------------


def test_classify_tools_have_anthropic_shape():
    assert len(CLASSIFY_TOOLS) == 2
    for tool in CLASSIFY_TOOLS:
        assert "name" in tool
        assert "description" in tool
        assert "input_schema" in tool
        schema = tool["input_schema"]
        assert schema["type"] == "object"
        assert "required" in schema
        assert "properties" in schema


def test_classify_tools_names():
    names = {t["name"] for t in CLASSIFY_TOOLS}
    assert "fetch_official_text" in names
    assert "record_classification" in names


def test_record_classification_tool_has_verdict_enum():
    tool = next(t for t in CLASSIFY_TOOLS if t["name"] == "record_classification")
    verdict_prop = tool["input_schema"]["properties"]["verdict"]
    assert set(verdict_prop["enum"]) == {"relevant", "not_relevant", "uncertain"}
