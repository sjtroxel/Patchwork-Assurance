import httpx
import streamlit as st

from patchwork_assurance.config import settings
from patchwork_assurance.ui.chrome import render_chrome, render_footer

# page_icon (the favicon) is deliberately left default - branding is Phase 4.
st.set_page_config(page_title="Patchwork Assurance")

st.title("Patchwork Assurance")
render_chrome()

st.write(
    "Phase 0 spine. The button below proves the UI -> API -> core wiring works end to end. "
    "Nothing here is legally meaningful yet; the wiring is the deliverable."
)

if st.button("Check system status"):
    try:
        response = httpx.get(f"{settings.api_base_url}/health", timeout=10.0)
        response.raise_for_status()
        st.success("API reachable.")
        st.json(response.json())
    except httpx.HTTPError as exc:
        st.error(f"Could not reach the API at {settings.api_base_url}: {exc}")

render_footer()
