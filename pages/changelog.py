import streamlit as st
from pathlib import Path
from menu import menu
if "current_page" not in st.session_state:
    st.session_state.current_page = "changelog"
def render_about_page()-> None:
    st.session_state.current_page = "changelog"
    menu()
    with st.container():
        st.markdown(Path("changelog.md").read_text())
if 'authenticated' in st.session_state and st.session_state['authenticated']:
    render_about_page()