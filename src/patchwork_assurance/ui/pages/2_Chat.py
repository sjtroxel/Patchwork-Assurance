import json

import streamlit as st

from patchwork_assurance.ui import client
from patchwork_assurance.ui.chrome import render_chrome, render_footer

st.set_page_config(
    page_title="Patchwork Assurance — Chat",
    page_icon="src/patchwork_assurance/ui/assets/favicon.svg",
    layout="centered",
)
st.logo("src/patchwork_assurance/ui/assets/logo.svg")
render_chrome()

st.title("Ask a question")
st.write(
    "Ask about Colorado SB 26-189 or Connecticut SB 5. "
    "Answers are grounded in the statute text with citations. Not legal advice."
)

if "messages" not in st.session_state:
    st.session_state.messages = []

for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

if prompt := st.chat_input("Ask about Colorado or Connecticut AI rules…"):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        sources: dict | None = None
        error: dict | None = None

        def _token_gen():
            global sources, error
            try:
                for ev, data in client.stream_chat(st.session_state.messages):
                    if ev == "token":
                        yield data
                    elif ev == "sources":
                        sources = json.loads(data)
                    elif ev == "error":
                        error = json.loads(data)
            except client.APIError as exc:
                st.error(str(exc))
                st.stop()

        full = st.write_stream(_token_gen())

        if error:
            st.error(error.get("detail", "The answer could not be completed."))
        else:
            st.session_state.messages.append({"role": "assistant", "content": full})
            if sources:
                cites = sources.get("citations", [])
                if cites:
                    st.caption("Sources: " + " · ".join(cites))
                disclaimer = sources.get("disclaimer", "")
                if disclaimer:
                    st.caption(disclaimer)

render_footer()
