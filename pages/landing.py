import streamlit as st
from astrapy import DataAPIClient

WELCOME_MESSAGE: str = "Welcome to ClerkGPT!"

def render_landing_page():
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
    if "made_attempt" not in st.session_state:
        st.session_state["made_attempt"] = False

    def login_screen():
        st.session_state.current_page = "landing"
        c1, c2, c3 = st.columns([1, 2, 1])
        with c2:
            st.image("images/logo.png")
            if st.button("Log in with Google"):
                st.login()
            st.session_state["made_attempt"] = True

    allowed_emails = st.secrets["allowed_users"]["emails"]

    if not getattr(st.user, "is_logged_in", False):
        login_screen()
        st.stop()
    else:
        user_email = getattr(st.user, "email", None)
        client = DataAPIClient(st.secrets['astra']['ASTRA_COLLECTION_USERNAME_TOKEN'])
        db = client.get_database_by_api_endpoint(st.secrets['astra']['ASTRA_DB_API_ENDPOINT'])
        table = db.get_table(st.secrets['astra']['ASTRA_COLLECTION_USERNAME_DB'])
        result = table.find_one({'users': user_email})
        # Perform a query to check if the user is in the database

        if result:
            st.session_state["authenticated"] = True
            st.switch_page("pages/chat.py")
        else:
            st.session_state["authenticated"] = False
            st.error("You are not authorized to use this app.")
render_landing_page()