"""Phase 9 Batch 2 — assess + fetch (offline only; StubLLM tool_script, no network, no tokens).

Key assertions:
- assess_change raises ValueError on an unchanged source (cost-control keystone)
- StubLLM tool_script drives the real dispatch (fetch + record_classification)
- AssessResult carries the verdict, reason, and fetched official text
- "uncertain" is the safe default when the LLM never calls record_classification
- CLASSIFY_TOOLS has the correct Anthropic tool shape
"""

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
# PDF official text falls back to descriptive note
# ---------------------------------------------------------------------------


def test_assess_change_pdf_content_type_returns_note():
    pdf_source = SourceEntry(
        jurisdiction="co",
        url="https://leg.colorado.gov/bills/sb26-189",
        official_url="https://leg.colorado.gov/bill_files/116489/download",
        kind="pdf",
    )
    pdf_changed = PollResult(source=pdf_source, changed=True, new_hash="x")

    class _PdfClient:
        def get(self, url: str, **kwargs) -> _FakeResponse:
            return _FakeResponse(b"%PDF-1.4 binary content", content_type="application/pdf")

    llm = StubLLM(
        text="Noted PDF.",
        tool_script=[
            ("fetch_official_text", {"url": pdf_source.official_url}),
            (
                "record_classification",
                {"verdict": "uncertain", "reason": "PDF; needs manual review."},
            ),
        ],
    )

    result = assess_change(pdf_changed, llm, http_client=_PdfClient())

    assert result.official_text is not None
    assert "PDF" in result.official_text
    assert result.verdict == "uncertain"


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
