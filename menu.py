import streamlit as st
def menu()-> None:
    st.sidebar.image("images/logo.png")
    st.sidebar.header(f"Welcome, {st.user.name}!")
    if st.sidebar.button("Log out"):
        st.logout()
        st.session_state["authenticated"] = False
        st.session_state["made_attempt"] = False
        # --- Optional: Reset conversation ---
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 'chat'
    if st.session_state.current_page == 'chat':
        if st.sidebar.button("Reset Conversation"):
            st.session_state.messages = []
    st.sidebar.page_link("pages/about.py", label="About", icon="ℹ️")
    st.sidebar.page_link("pages/chat.py", label="Chat", icon="🤖")
    st.sidebar.page_link("pages/faq.py", label="FAQ", icon="❓")
    st.sidebar.page_link("pages/changelog.py", label="Changelog", icon="📜")
    st.sidebar.page_link("pages/doc_catalog.py", label="Document Catalog", icon="📚")