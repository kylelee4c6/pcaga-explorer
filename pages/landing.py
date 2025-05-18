import streamlit as st

WELCOME_MESSAGE: str = "Welcome to ClerkGPT!"
if "current_page" not in st.session_state:
    st.session_state.current_page = "landing"
def render_landing_page() -> None:
    st.session_state.current_page = "landing"
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:

        st.image("images/logo.png")

        get_started = st.button("Get Started", type="primary")
        if get_started:
            st.switch_page('pages/about.py')
render_landing_page()