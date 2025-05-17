import streamlit as st
from pathlib import Path
WELCOME_MESSAGE: str = "Welcome to ClerkGPT!"
from menu import menu
def render_about_page()-> None:
    menu()
    with st.container():
        st.markdown(Path("pages/about.md").read_text())
render_about_page()