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
    "Describe your situation for a grounded, educational summary of how Colorado SB 26-189 "
    "and Connecticut SB 5 may apply. Not legal advice.",
)

DOMAIN_LABELS = {
    "education": "Education",
    "employment": "Employment",
    "housing": "Housing",
    "financial_lending": "Financial / lending",
    "insurance": "Insurance",
    "health_care": "Health care",
    "government_services": "Government services",
}


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
            st.caption(f"{n.get('kind', '')} — {n.get('jurisdiction', '')}")
            st.code(n.get("text", ""), language=None)

    deadlines = memo.get("deadline_checklist", [])
    if deadlines:
        st.subheader("Deadlines")
        st.dataframe(deadlines, hide_index=True, use_container_width=True)

    if memo.get("disclaimer"):
        st.warning(memo["disclaimer"])


with st.form("situation"):
    jurisdictions = st.multiselect(
        "Where do you operate, employ, or serve people?",
        ["Colorado", "Connecticut"],
    )
    domains = st.multiselect(
        "Which decisions does your AI touch?",
        list(DOMAIN_LABELS),
        format_func=lambda s: DOMAIN_LABELS[s],
    )
    roles = st.multiselect("Your role", ["developer", "deployer"])
    uses_ai = st.toggle("We use AI to make or materially influence these decisions", value=True)
    notes = st.text_area("Anything else? (optional)")
    submitted = st.form_submit_button("Generate memo")

if submitted:
    situation = {
        "jurisdictions": jurisdictions,
        "decision_domains": domains,
        "roles": roles,
        "uses_ai_in_decisions": uses_ai,
        "notes": notes,
    }
    try:
        with st.spinner("Analyzing against the statute text…"):
            memo = client.analyze(situation)
        _render_memo(memo)
    except client.APIError as exc:
        st.error(str(exc))

render_footer()
