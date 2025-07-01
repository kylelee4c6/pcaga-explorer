import streamlit as st

def main():
    st.set_page_config(layout = "wide")
    st.switch_page("pages/landing.py")
    #st.write("The app is currently down at the moment.")

if __name__ == "__main__":
    main()