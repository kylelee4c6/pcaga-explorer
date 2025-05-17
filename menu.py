import streamlit as st

def menu()-> None:
    st.set_page_config(layout = "wide")
    st.sidebar.image("images/logo.png")
    st.sidebar.title("Welcome to ClerkGPT!")
    st.sidebar.page_link("pages/about.py", label="About", icon="ℹ️")
    st.sidebar.page_link("pages/chat.py", label="Chat", icon="🤖")
    st.sidebar.page_link("pages/faq.py", label="FAQ", icon="❓")
