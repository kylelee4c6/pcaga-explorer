import streamlit as st
if "current_page" not in st.session_state:
    st.session_state.current_page = "chat"
def menu()-> None:
    try:
        st.set_page_config(layout = "wide")
    except:
        pass
    st.sidebar.image("images/logo.png")
    st.sidebar.title("Welcome to ClerkGPT!")
    st.sidebar.page_link("pages/about.py", label="About", icon="ℹ️")
    st.sidebar.page_link("pages/chat.py", label="Chat", icon="🤖")
    st.sidebar.page_link("pages/faq.py", label="FAQ", icon="❓")
    st.sidebar.page_link("pages/changelog.py", label="Changelog", icon="📜")