import streamlit as st

from patchwork_assurance.ui import client
from patchwork_assurance.ui.chrome import (
    inject_brand_css,
    render_chrome,
    render_footer,
    render_hero,
    render_seam,
)

inject_brand_css()
render_chrome()
render_hero(
    "Compliance Memo",
    "Describe your situation for a grounded, educational summary of how Colorado SB 26-189 and "
    "Connecticut SB 5 may reach your business, even from out of state. Not legal advice.",
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
    "jurisdictions": ["Colorado", "Connecticut"],
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


def _render_memo(memo: dict) -> None:
    SCOPE_BOX = {"yes": st.success, "uncertain": st.info, "no": st.warning}

    render_seam()
    for law in memo.get("per_law", []):
        with st.expander(law.get("short_name", "Law"), expanded=True):
            scope = law.get("in_scope", "")
            box = SCOPE_BOX.get(scope, st.write)
            box(f"In scope: {scope.upper() if scope else 'UNKNOWN'}")
            st.write(law.get("why", ""))
            for ob in law.get("obligations", []):
                st.markdown(f"- {ob.get('text', '')}  \n  *{ob.get('citation', '')}*")
            if law.get("effective_dates"):
                st.caption("Effective: " + ", ".join(law["effective_dates"]))

    notices = memo.get("draft_notices", [])
    if notices:
        st.subheader("Draft notice language")
        for n in notices:
            st.caption(f"{n.get('kind', '')} ({n.get('jurisdiction', '')})")
            st.code(n.get("text", ""), language=None)

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
        with st.spinner("Analyzing against the statute text…"):
            memo = client.analyze(situation)
        _render_memo(memo)
    except client.APIError as exc:
        st.error(str(exc))

render_footer()
