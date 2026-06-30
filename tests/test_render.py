"""Phase 11 — the shared ComplianceMemo -> HTML renderer + executive summary (core/render.py).

Pure functions, so the tests are direct and offline (no LLM, zero spend). They lock the legal
boundary that the PDF carries: the disclaimer + the dated "as of" stamp, per-obligation citations,
hedged (never guaranteeing) summary language, and HTML-escaping of untrusted model output.
"""

from datetime import date

from patchwork_assurance.core.contracts import (
    ComplianceMemo,
    DeadlineItem,
    DraftNotice,
    LawFinding,
    MemoObligation,
    Situation,
)
from patchwork_assurance.core.prompts import DISCLAIMER
from patchwork_assurance.core.render import executive_summary, memo_to_html

# Words that assert authoritative legal judgment or a guarantee — must never appear in generated
# copy (.claude/rules/legal-content.md; mirrors the prohibited list in core.prompts).
_PROHIBITED = ("guarantee", "you are compliant", "you must comply", "we certify")


def _memo() -> ComplianceMemo:
    return ComplianceMemo(
        per_law=[
            LawFinding(
                law_id="co-sb26-189",
                short_name="CO SB 26-189",
                in_scope="yes",
                why="Likely applies: the tool materially influences employment decisions.",
                obligations=[
                    MemoObligation(
                        text="Complete an impact assessment for the deployed ADMT.",
                        citation="Colorado § 6-1-1703",
                    )
                ],
                effective_dates=["Effective 2026-06-30"],
            ),
            LawFinding(
                law_id="ca-ccpa-admt",
                short_name="CA CCPA ADMT Regs",
                in_scope="no",
                why="Does not appear to apply: no California nexus was indicated.",
            ),
        ],
        draft_notices=[
            DraftNotice(kind="Consumer ADMT notice", jurisdiction="Colorado", text="We use ADMT...")
        ],
        deadline_checklist=[
            DeadlineItem(date="2026-06-30", what="Deployer duties in effect.", law="CO SB 26-189")
        ],
        next_steps=["Inventory your automated tools.", "Consult a licensed attorney."],
        disclaimer=DISCLAIMER,
    )


def _situation() -> Situation:
    return Situation(
        home_state="Missouri",
        jurisdictions=["Colorado", "Connecticut"],
        decision_domains=["employment", "housing"],
        roles=["deployer"],
        ai_use="yes",
    )


# ---- executive_summary ----
def test_executive_summary_counts_and_hedging():
    line = executive_summary(_memo(), _situation())
    assert "considers 2 AI/automated-decision laws" in line
    assert "1 appear to be in scope" in line  # only CO is yes/uncertain
    assert "2 states where you indicated a nexus" in line
    assert "employment, housing decisions" in line
    assert "2026-06-30" in line  # earliest deadline surfaced
    assert "appear to be in scope" in line  # hedged verb
    lower = line.lower()
    assert all(bad not in lower for bad in _PROHIBITED)


def test_executive_summary_without_situation_degrades():
    line = executive_summary(_memo(), None)
    assert "considers 2 AI/automated-decision laws" in line
    assert "nexus" not in line  # the situation-derived clause is omitted


def test_executive_summary_zero_in_scope():
    memo = _memo()
    for f in memo.per_law:
        f.in_scope = "no"
    memo.deadline_checklist = []
    line = executive_summary(memo, _situation())
    assert "none appear to be in scope" in line
    assert "not legal advice" in line.lower()


# ---- memo_to_html ----
def test_memo_to_html_has_every_section():
    html = memo_to_html(
        _memo(), situation=_situation(), generated_on=date(2026, 6, 30), corpus_as_of="2026-06-27"
    )
    # per-law verdict + reasoning
    assert "CO SB 26-189" in html and "Likely applies" in html
    assert "May apply" in html or "Does not appear to apply" in html
    # obligation text WITH its citation attached
    assert "Complete an impact assessment for the deployed ADMT." in html
    assert "Colorado § 6-1-1703" in html
    # draft notice, deadline, next steps
    assert "Consumer ADMT notice" in html and "We use ADMT..." in html
    assert "Deployer duties in effect." in html
    assert "Inventory your automated tools." in html


def test_memo_to_html_carries_disclaimer_and_dated_stamp():
    """The not-legal-advice guarantee, as a test: the disclaimer text and an 'as of [date]' framing
    are present and prominent in the rendered document (locks .claude/rules/legal-content.md)."""
    html = memo_to_html(
        _memo(), situation=_situation(), generated_on=date(2026, 6, 30), corpus_as_of="2026-06-27"
    )
    assert DISCLAIMER in html
    assert "Not legal advice." in html
    assert "as of the dates above" in html
    assert "2026-06-30" in html  # generated date (header + running footer)
    assert "2026-06-27" in html  # corpus-as-of stamp
    assert 'content: "Generated 2026-06-30"' in html  # running footer on every page


def test_memo_to_html_escapes_untrusted_model_text():
    memo = _memo()
    memo.per_law[0].why = "<script>alert('x')</script> & co"
    html = memo_to_html(memo)
    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html
    assert "&amp; co" in html


def test_memo_to_html_defaults_to_today_without_stamps():
    html = memo_to_html(_memo())
    assert date.today().isoformat() in html


def test_memo_to_html_omits_empty_sections():
    bare = ComplianceMemo(
        per_law=[LawFinding(law_id="x", short_name="X", in_scope="no", why="No.")],
        disclaimer=DISCLAIMER,
    )
    html = memo_to_html(bare)
    assert "Draft Notice Language" not in html
    assert "III. Deadlines" not in html
    assert "Your Next Steps" not in html
    assert "I. Laws Considered" in html  # always present
