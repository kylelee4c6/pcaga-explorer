import streamlit as st
from pathlib import Path
from menu import menu
def render_about_page()-> None:
    menu()
    with st.container():
        st.markdown(Path("pages/faq.md").read_text())
render_about_page()