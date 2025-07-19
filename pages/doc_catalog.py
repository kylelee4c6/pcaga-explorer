import streamlit as st
import pandas as pd
from menu import menu

@st.cache_resource(show_spinner=False)
def get_doc_catalog():
    data_catalog = pd.read_csv("notebooks/files/pdf_metadata.csv")
    return data_catalog[['filename','title', 'pdf_url', 'source_url', 'creationDate']]

def render_doc_catalog():
    st.title("Document Catalog")
    menu()
    st.write("This page will display the catalog of documents available in the system.")
    st.dataframe(get_doc_catalog())

render_doc_catalog()