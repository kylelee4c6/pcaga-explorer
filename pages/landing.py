import streamlit as st

WELCOME_MESSAGE: str = "Welcome to ClerkGPT!"

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
def render_landing_page() -> None:
    st.session_state.current_page = "landing"
    st.session_state['made_attempt'] = False
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:

        st.image("images/logo.png")
        username = st.text_input("Username", placeholder="Enter your username")
        password = st.text_input("Password", type="password", placeholder="Enter your password")
        valid_users = st.secrets['account']['USER_NAME']
        if st.button("Login"):
            st.session_state['made_attempt'] = True
            if username in valid_users and password == st.secrets['account']['PASSWORD']:
                st.session_state['authenticated'] = True
                st.success("Login successful!")
                st.session_state.current_page = "chat"
                st.switch_page('pages/chat.py')
            else:
                st.error("Invalid username or password. Please try again.")
if not st.session_state['authenticated']:
    render_landing_page()
    st.stop()
