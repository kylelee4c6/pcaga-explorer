import streamlit as st
if "current_page" not in st.session_state:
    st.session_state.current_page = "chat"
def menu()-> None:
    st.set_page_config(layout = "wide")
    st.sidebar.image("images/logo.png")
    st.sidebar.title("Welcome to ClerkGPT!")
    st.sidebar.page_link("pages/about.py", label="About", icon="ℹ️")
    st.sidebar.page_link("pages/chat.py", label="Chat", icon="🤖")
    st.sidebar.page_link("pages/faq.py", label="FAQ", icon="❓")
    if st.session_state.current_page == "chat":
        st.sidebar.number_input(
            label="Select the number of references to consider.",
            min_value=0,
            max_value=10,
            value=5,
            step=1,
            key = "num_references"
    )
