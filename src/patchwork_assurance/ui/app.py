import streamlit as st

from patchwork_assurance.ui.chrome import inject_brand_css

# Navigation entry (Phase 4.5 M4): a top nav instead of a sidebar for two pages, with
# real page titles ("Memo" not "app"). Page content lives in memo.py / chat.py; the legal
# chrome, brand CSS, and hero are rendered per page so every surface carries them.
st.set_page_config(
    page_title="Patchwork Assurance",
    page_icon="src/patchwork_assurance/ui/assets/favicon.svg",
    layout="centered",
)
# Full lockup (mark + outlined wordmark) in the top bar. No icon_image: in top-nav mode
# Streamlit renders icon_image (the compact form) in the header, which would show only the
# square mark. The wordmark is outlined to vector paths (M5.3) so it renders font-independently;
# sizing is enforced in the brand CSS layer (chrome.py).
st.logo("src/patchwork_assurance/ui/assets/logo.svg", size="large")
inject_brand_css()  # ensure the logo-sizing CSS is present where the header renders

pages = [
    st.Page("memo.py", title="Memo", default=True),
    st.Page("chat.py", title="Chat"),
]
st.navigation(pages, position="top").run()
