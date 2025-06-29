import streamlit as st
from pathlib import Path
WELCOME_MESSAGE: str = "Welcome to ClerkGPT!"
from menu import menu
if "current_page" not in st.session_state:
    st.session_state.current_page = "about"
def render_about_page()-> None:
    st.session_state.current_page = "about"
    menu()
    with st.container():
        st.markdown(Path("pages/about.md").read_text())
if 'authenticated' in st.session_state and st.session_state['authenticated']:
    render_about_page()