"""AppTest smoke tests for the two UI pages — fully offline, API mocked."""

import json
from unittest.mock import patch

import pytest
from streamlit.testing.v1 import AppTest

# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

# The memo page loads its form vocab from GET /meta; stub it so tests never touch the network.
FAKE_META = {
    "jurisdictions": ["Colorado", "Connecticut"],
    "decision_domains": ["employment", "financial_lending", "housing", "health_care"],
    "roles": ["deployer", "developer"],
}


@pytest.fixture(autouse=True)
def _stub_meta():
    quota = {"limit": 2, "used": 0, "remaining": 2}
    with (
        patch("patchwork_assurance.ui.client.get_meta", return_value=FAKE_META),
        patch("patchwork_assurance.ui.client.get_memo_quota", return_value=quota),
    ):
        yield


SAMPLE_MEMO = {
    "per_law": [
        {
            "law_id": "co-sb26-189",
            "short_name": "CO SB 26-189",
            "in_scope": "yes",
            "why": "Deployer of an ADMT.",
            "obligations": [{"text": "Provide notice.", "citation": "Colorado § 6-1-1704"}],
            "effective_dates": ["2027-01-01"],
        }
    ],
    "draft_notices": [],
    "deadline_checklist": [],
    "disclaimer": "Educational analysis, not legal advice.",
}

SOURCES_JSON = json.dumps({"citations": ["CO § 6-1-1704"], "disclaimer": "Not legal advice."})


def _mock_stream(messages, **_):
    yield ("token", "Hello ")
    yield ("token", "world.")
    yield ("sources", SOURCES_JSON)


# ---------------------------------------------------------------------------
# Memo page (app.py)
# ---------------------------------------------------------------------------


def test_memo_page_chrome_present():
    at = AppTest.from_file("src/patchwork_assurance/ui/memo.py").run()
    assert not at.exception
    warnings = [w.value for w in at.warning]
    assert any("not legal advice" in w.lower() for w in warnings)


def test_memo_page_form_exists():
    at = AppTest.from_file("src/patchwork_assurance/ui/memo.py").run()
    assert not at.exception
    assert len(at.button) == 1
    assert at.button[0].label == "Generate memo"
    assert len(at.multiselect) == 2  # nexus states + decision domains
    assert len(at.radio) == 2  # role + AI-use
    assert len(at.selectbox) == 1  # home state


def test_memo_page_renders_memo_on_submit():
    at = AppTest.from_file("src/patchwork_assurance/ui/memo.py").run()
    at.multiselect[0].set_value(["Colorado"])  # nexus
    at.multiselect[1].set_value(["employment"])  # decision domain
    # role + AI-use radios keep their defaults (deployer / "Yes")

    # Force the PDF path to degrade (raise) so no st.download_button renders: a real one trips a
    # documented AppTest false-positive ("Forms cannot be nested", discuss.streamlit.io/t/.../62277).
    # Patch the SOURCE symbol (ui.pdf) — AppTest runs the page in a fresh namespace, so patching
    # ui.memo would not apply. The real PDF render is locked in test_pdf.py.
    with (
        patch("patchwork_assurance.ui.client.analyze", return_value=SAMPLE_MEMO),
        patch("patchwork_assurance.ui.pdf.memo_pdf_bytes", side_effect=RuntimeError("no libs")),
    ):
        at.button[0].click().run()

    assert not at.exception
    expander_labels = [e.label for e in at.expander]
    assert "CO SB 26-189" in expander_labels
    warnings = [w.value for w in at.warning]
    assert any("Educational analysis" in w for w in warnings)
    # Phase 11: the deterministic, hedged executive-summary line renders atop the memo (st.info)...
    infos = [i.value for i in at.info]
    assert any("appear to be in scope" in i for i in infos)
    # ...and the PDF export is wired into the memo render (degraded to its caption here, no libs in test).
    assert any("unavailable" in c.value for c in at.caption)


def test_memo_page_draft_notices_render_as_expanders():
    """Phase 11: each draft notice is its own collapsible expander (label = kind + jurisdiction)."""
    memo = {
        **SAMPLE_MEMO,
        "draft_notices": [
            {"kind": "Consumer notice", "jurisdiction": "Colorado", "text": "We use ADMT..."}
        ],
    }
    at = AppTest.from_file("src/patchwork_assurance/ui/memo.py").run()
    at.multiselect[0].set_value(["Colorado"])
    at.multiselect[1].set_value(["employment"])

    with (
        patch("patchwork_assurance.ui.client.analyze", return_value=memo),
        # degrade the PDF path so no download widget renders (AppTest nested-form false-positive)
        patch("patchwork_assurance.ui.pdf.memo_pdf_bytes", side_effect=RuntimeError("no libs")),
    ):
        at.button[0].click().run()

    assert not at.exception
    assert "Consumer notice (Colorado)" in [e.label for e in at.expander]


def test_memo_page_shows_error_when_api_down():
    from patchwork_assurance.ui.client import APIError

    at = AppTest.from_file("src/patchwork_assurance/ui/memo.py").run()
    at.multiselect[0].set_value(["Colorado"])  # nexus
    at.multiselect[1].set_value(["employment"])  # decision domain
    # role + AI-use radios keep their defaults (deployer / "Yes")

    with patch(
        "patchwork_assurance.ui.client.analyze",
        side_effect=APIError("Could not reach the analysis service."),
    ):
        at.button[0].click().run()

    assert not at.exception
    errors = [e.value for e in at.error]
    assert any("Could not reach" in e for e in errors)


# ---------------------------------------------------------------------------
# Chat page (pages/2_Chat.py)
# ---------------------------------------------------------------------------


def test_nav_entry_runs():
    """The st.navigation entry (top nav, renamed pages) loads without error."""
    at = AppTest.from_file("src/patchwork_assurance/ui/app.py").run()
    assert not at.exception


def test_chat_page_chrome_present():
    at = AppTest.from_file("src/patchwork_assurance/ui/chat.py").run()
    assert not at.exception
    warnings = [w.value for w in at.warning]
    assert any("not legal advice" in w.lower() for w in warnings)


def test_chat_page_input_exists():
    at = AppTest.from_file("src/patchwork_assurance/ui/chat.py").run()
    assert not at.exception
    assert len(at.chat_input) == 1


def test_chat_page_streams_answer_and_shows_sources():
    at = AppTest.from_file("src/patchwork_assurance/ui/chat.py").run()
    at.chat_input[0].set_value("What must a Colorado deployer disclose?")

    with patch("patchwork_assurance.ui.client.stream_chat", side_effect=_mock_stream):
        at.run()

    assert not at.exception
    roles = [m.name for m in at.chat_message]
    assert "user" in roles
    assert "assistant" in roles
    captions = [c.value for c in at.caption]
    assert any("CO § 6-1-1704" in c for c in captions)
    assert any("Not legal advice." in c for c in captions)
