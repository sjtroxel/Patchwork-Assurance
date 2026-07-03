import json

import streamlit as st

from patchwork_assurance.core.contracts import ComplianceMemo, Situation
from patchwork_assurance.core.render import VERDICT_LABEL, executive_summary
from patchwork_assurance.ui import client
from patchwork_assurance.ui.chrome import (
    inject_brand_css,
    render_chrome,
    render_footer,
    render_hero,
    render_seam,
)
from patchwork_assurance.ui.pdf import memo_filename, memo_pdf_bytes

inject_brand_css()
render_chrome()
render_hero(
    "Compliance Memo",
    "Describe your situation for a grounded, educational summary of how the state AI laws in our "
    "corpus* may reach your business, even from out of state. Not legal advice.",
    note="* The corpus also includes New York City's Local Law 144 (the AEDT bias-audit law) — "
    "a city large enough to sit beside the states.",
)

# Business-language labels for the consequential-decision domains (presentation only). The form
# surfaces the intersection of these with the corpus's covered domains, so a law's broader provisions
# (e.g. CT's AI-companion/generative-AI/frontier rules) are handled by a memo note, not a form gate.
DOMAIN_LABELS = {
    "employment": "Employment (hiring, promotion, discipline, termination, training)",
    "housing": "Housing",
    "financial_lending": "Financial / lending",
    "insurance": "Insurance",
    "health_care": "Health care",
    "education": "Education",
    "government_services": "Government services",
}

# Business-language role choices → the statutory roles the scope engine expects.
ROLE_OPTIONS = {
    "We use a third-party AI tool": ["deployer"],
    "We build or sell the AI tool": ["developer"],
    "Both": ["developer", "deployer"],
    "Not sure": ["deployer"],  # most businesses are deployers; cautious default
}

AI_USE_OPTIONS = {"Yes": "yes", "No": "no", "Not sure": "unsure"}

# Friendly labels for the model ids that flow through the observability panel (Phase 12 §9). The panel
# names which model produced each contribution; the ids arrive from config via the AgentEvents, so the
# UI hardcodes no model — an unmapped id falls back to its raw string so a future model still shows
# something truthful.
MODEL_LABELS = {
    "claude-sonnet-5": "Sonnet 5",
    "claude-opus-4-8": "Opus 4.8",
    "claude-haiku-4-5": "Haiku 4.5",
}
_VERDICT_MARK = {"grounded": "✓", "flagged": "⚠", "dropped": "✗"}


def _model_label(model_id: str) -> str:
    return MODEL_LABELS.get(model_id, model_id or "model")


def _agent_line(ev: dict, names: dict[str, str]) -> str | None:
    """One human-readable panel line for an AgentEvent (a dict from the SSE JSON). None when there is
    nothing to show (the terminal 'done')."""
    kind = ev.get("kind", "")
    model = _model_label(ev.get("model", ""))
    law_id = ev.get("law_id", "")
    detail = ev.get("detail", "")
    if kind == "analyst_start":
        names[law_id] = detail or law_id  # remember the short_name for the matching done line
        return f"Analyzing {detail or law_id} · {model}…"
    if kind == "analyst_done":
        ms = ev.get("ms")
        suffix = f" ({ms:.0f} ms)" if isinstance(ms, int | float) else ""
        return f"✓ {names.get(law_id, law_id)} analyzed{suffix}"
    if kind == "review_verdict":
        # detail is e.g. "grounded: Colorado § 6-1-1704" or "dropped (fabricated citation): …".
        verdict = detail.split()[0].rstrip(":") if detail else ""
        return f"{_VERDICT_MARK.get(verdict, '·')} {detail} (reviewed by {model})"
    if kind == "review_summary":
        return f"Executive summary written by {model}"
    return None


def _run_streaming_memo(situation: dict, client_ip: str) -> dict | None:
    """Drive POST /analyze/stream, showing a live fold-out that names the model behind each step (this
    is what makes the multi-agent latency legible — the answer Phase 11 deferred to here). Returns the
    ComplianceMemo dict, or None if the stream ended in a terminal error event. Raises client.APIError
    if the connection fails before streaming starts (surfaced by the caller)."""
    memo: dict | None = None
    names: dict[str, str] = {}
    header = {"analyst": False, "reviewer": False}
    with st.status("Generating your memo…", expanded=True) as status:
        for ev_name, data in client.analyze_stream(situation, client_ip=client_ip):
            if ev_name == "agent":
                ev = json.loads(data)
                kind = ev.get("kind", "")
                if kind == "analyst_start" and not header["analyst"]:
                    st.caption(f"Analysts: {_model_label(ev.get('model', ''))}")
                    header["analyst"] = True
                if kind.startswith("review") and not header["reviewer"]:
                    st.caption(f"Reviewer: {_model_label(ev.get('model', ''))}")
                    header["reviewer"] = True
                line = _agent_line(ev, names)
                if line:
                    st.write(line)
            elif ev_name == "memo":
                memo = json.loads(data)
            elif ev_name == "error":
                status.update(label="Memo failed", state="error", expanded=True)
                st.error(json.loads(data).get("detail", "The memo could not be completed."))
                return None
        status.update(label="Memo ready", state="complete", expanded=False)
    return memo


# US states (+ DC) for the home-state field. Full names so a regulating home state (e.g. "Colorado")
# matches the corpus jurisdiction and auto-counts as a nexus (handled in core/scope.py).
US_STATES = [
    "Alabama",
    "Alaska",
    "Arizona",
    "Arkansas",
    "California",
    "Colorado",
    "Connecticut",
    "Delaware",
    "District of Columbia",
    "Florida",
    "Georgia",
    "Hawaii",
    "Idaho",
    "Illinois",
    "Indiana",
    "Iowa",
    "Kansas",
    "Kentucky",
    "Louisiana",
    "Maine",
    "Maryland",
    "Massachusetts",
    "Michigan",
    "Minnesota",
    "Mississippi",
    "Missouri",
    "Montana",
    "Nebraska",
    "Nevada",
    "New Hampshire",
    "New Jersey",
    "New Mexico",
    "New York",
    "North Carolina",
    "North Dakota",
    "Ohio",
    "Oklahoma",
    "Oregon",
    "Pennsylvania",
    "Rhode Island",
    "South Carolina",
    "South Dakota",
    "Tennessee",
    "Texas",
    "Utah",
    "Vermont",
    "Virginia",
    "Washington",
    "West Virginia",
    "Wisconsin",
    "Wyoming",
]

# Used only if /meta is unreachable, so the form still renders.
_FALLBACK_META = {
    "jurisdictions": [
        "California",
        "Colorado",
        "Connecticut",
        "Illinois",
        "New Jersey",
        "New York City",
        "Texas",
    ],
    "decision_domains": list(DOMAIN_LABELS),
    "roles": ["deployer", "developer"],
}


def _or_join(names: list[str]) -> str:
    """Grammatical join of the regulating-state names for copy, derived from the corpus (stays
    correct when a jurisdiction is added). e.g. ['Colorado','Connecticut'] -> 'Colorado or Connecticut'."""
    if not names:
        return "these"
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} or {names[1]}"
    return ", ".join(names[:-1]) + f", or {names[-1]}"


def _load_meta() -> dict:
    """Corpus-derived form vocab from GET /meta, cached for the session; falls back if the API is
    unreachable so the form is never blocked."""
    if "meta" not in st.session_state:
        try:
            st.session_state.meta = client.get_meta()
        except client.APIError:
            st.session_state.meta = _FALLBACK_META
    return st.session_state.meta


def _browser_ip() -> str:
    """The visitor's browser IP, forwarded to the API so the memo limit keys per-user (the API
    otherwise sees only the UI server). `st.context.ip_address` is the real client IP behind Railway;
    fall back to the X-Forwarded-For header. Returns '' if unavailable (then the API uses its socket
    peer)."""
    try:
        ip = getattr(st.context, "ip_address", None)
        if ip:
            return ip
        xff = st.context.headers.get("X-Forwarded-For", "")
        return xff.split(",")[0].strip() if xff else ""
    except Exception:
        return ""


def _render_pdf_button(typed: ComplianceMemo, typed_situation: Situation) -> None:
    """Forwardable PDF (Phase 11) — built in-session from the memo already on screen (no re-send, no
    re-spend), with the memo's own dated stamps. The export is a nice-to-have: if PDF rendering is
    unavailable in some environment, degrade gracefully rather than break the memo view.

    Note for tests: Streamlit's AppTest raises a documented false-positive "Forms cannot be nested in
    other forms" when it renders an st.download_button in the post-form-submit path
    (discuss.streamlit.io/t/.../62277). The real app is unaffected. AppTest runs the page in a fresh
    namespace, so the UI smoke tests force this path to degrade by patching the *source* symbol
    `patchwork_assurance.ui.pdf.memo_pdf_bytes` to raise (the caption renders instead of a widget); the
    real PDF path is locked in tests/test_pdf.py.
    """
    try:
        st.download_button(
            "Export to PDF",
            data=memo_pdf_bytes(typed, typed_situation),
            file_name=memo_filename(typed),
            mime="application/pdf",
        )
    except Exception:
        st.caption("PDF export is temporarily unavailable.")


def _render_memo(memo: dict, situation: dict) -> None:
    # Box color carries emotional truth for an anxious non-expert, not the raw enum: a law that does
    # NOT reach them is relief (success/green), an uncertain one is caution (warning/amber), and one
    # that DOES reach them is attention, not celebration (info/blue). The label text is the same hedged
    # VERDICT_LABEL the PDF uses (core/render.py), so the screen and the export read identically.
    SCOPE_BOX = {"no": st.success, "uncertain": st.warning, "yes": st.info}

    # Deterministic, hedged orientation atop the memo (Phase 11) — the same shared helper the PDF
    # uses, so the screen summary and the exported document read identically. The UI holds the memo
    # as a dict; reconstruct the typed pair so there's one typed path, no dict-vs-object drift.
    typed = ComplianceMemo.model_validate(memo)
    typed_situation = Situation.model_validate(situation)
    # Phase 12 seam (UI half): prefer the reviewer's natural-language summary when present (multi_agent
    # mode) and fall back to the deterministic Phase 11 line otherwise — same precedence as render.py.
    st.info(typed.summary or executive_summary(typed, typed_situation))
    _render_pdf_button(typed, typed_situation)

    render_seam()
    for law in memo.get("per_law", []):
        with st.expander(law.get("short_name", "Law"), expanded=True):
            scope = law.get("in_scope", "")
            box = SCOPE_BOX.get(scope, st.write)
            box(VERDICT_LABEL.get(scope, "Status unknown"))
            st.write(law.get("why", ""))
            for ob in law.get("obligations", []):
                st.markdown(f"- {ob.get('text', '')}  \n  *{ob.get('citation', '')}*")
            if law.get("effective_dates"):
                st.caption("Effective: " + ", ".join(law["effective_dates"]))

    notices = memo.get("draft_notices", [])
    if notices:
        st.subheader("Draft notice language")
        for n in notices:
            # Expander → a scannable list collapsed by default; st.code stays INSIDE so Streamlit's
            # built-in copy button is preserved (Phase 11 §6). wrap_lines wraps the notice prose (one
            # long paragraph) to multiple lines instead of a single horizontally-scrolling line.
            with st.expander(f"{n.get('kind', '')} ({n.get('jurisdiction', '')})"):
                st.code(n.get("text", ""), language=None, wrap_lines=True)

    deadlines = memo.get("deadline_checklist", [])
    if deadlines:
        st.subheader("Deadlines")
        st.dataframe(deadlines, hide_index=True, use_container_width=True)

    steps = memo.get("next_steps", [])
    if steps:
        st.subheader("Your next steps")
        st.caption("General orientation, not a compliance plan. Consult a licensed attorney.")
        for step in steps:
            st.markdown(f"- {step}")

    if memo.get("disclaimer"):
        st.warning(memo["disclaimer"])


meta = _load_meta()
domain_opts = [d for d in meta["decision_domains"] if d in DOMAIN_LABELS]
reach = _or_join(
    meta["jurisdictions"]
)  # e.g. "Colorado or Connecticut" — from the corpus, not hardcoded
client_ip = _browser_ip()
quota_slot = st.empty()  # filled after the submit handler so it reflects this run's generation

with st.form("situation"):
    home_state = st.selectbox(
        "Where is your business based?",
        US_STATES,
        index=None,
        placeholder="Select your state",
        help=f"Your home state may have no AI law of its own, but the {reach} laws may still reach you.",
    )
    jurisdictions = st.multiselect(
        "In which of these states do you have employees, job applicants, customers, or residents "
        "you make decisions about?",
        meta["jurisdictions"],
        help="Even one person may be enough. Reach is what matters, not where you're headquartered.",
    )
    domains = st.multiselect(
        "What kinds of decisions about people do you make?",
        domain_opts,
        format_func=lambda s: DOMAIN_LABELS.get(s, s.replace("_", " ").title()),
    )
    role_choice = st.radio("What's your relationship to the AI tool?", list(ROLE_OPTIONS), index=0)
    ai_choice = st.radio(
        "Do you use any tool that scores, ranks, screens, classifies, or recommends people?",
        list(AI_USE_OPTIONS),
        index=0,
        help="Examples: resume screeners, applicant tracking systems, credit or tenant scoring, "
        "ranking or recommendation engines.",
    )
    notes = st.text_area("Anything else about your situation? (optional)")
    submitted = st.form_submit_button("Generate memo")

if submitted:
    situation = {
        "home_state": home_state or "",
        "jurisdictions": jurisdictions,
        "decision_domains": domains,
        "roles": ROLE_OPTIONS[role_choice],
        "ai_use": AI_USE_OPTIONS[ai_choice],
        "notes": notes,
    }
    try:
        # Stream the multi-agent pipeline so the observability fold-out shows per-agent progress live.
        # Hold the in-session result in session_state (ephemeral, discarded with the session — the same
        # pattern already used for `meta`; no DB, no saved history, statelessness intact). This is what
        # lets the PDF download button work: st.download_button reruns the page on click (streamlit#3832),
        # and persisting the memo means that rerun re-renders it instead of wiping it back to the form.
        memo = _run_streaming_memo(situation, client_ip)
        if memo is not None:
            st.session_state.memo = memo
            st.session_state.memo_situation = situation
        else:
            st.session_state.pop("memo", None)  # terminal stream error already shown in the panel
    except client.APIError as exc:
        st.session_state.pop("memo", None)
        st.error(str(exc))

# Render the current in-session memo (from this submit or preserved across a download-button rerun).
if st.session_state.get("memo"):
    _render_memo(st.session_state.memo, st.session_state.memo_situation)

# Memo quota indicator (reflects this run's generation, if any). Read-only; never blocks the page.
try:
    _q = client.get_memo_quota(client_ip=client_ip)
    if _q.get("limit", 0) > 0:
        quota_slot.caption(f"{_q['remaining']} of {_q['limit']} compliance memos left today.")
except client.APIError:
    pass

render_footer()
