import streamlit as st
import os
from langchain_openai import ChatOpenAI
from langchain_astradb import AstraDBVectorStore
from astrapy.info import VectorServiceOptions
from urllib.parse import urlparse
from langchain.prompts import ChatPromptTemplate, SystemMessagePromptTemplate, HumanMessagePromptTemplate
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory
from menu import menu
# --- Memory setup ---
if "memory" not in st.session_state:
    st.session_state.memory = ConversationBufferMemory(
        memory_key="chat_history", return_messages=True,
        output_key="answer"  # This is important for the chain to return the answer
    )
if "messages" not in st.session_state:
    st.session_state.messages = []

@st.cache_resource(show_spinner=False)
def get_secrets_and_vector_store():
    secrets = st.secrets
    vector_store = AstraDBVectorStore(
        collection_name=secrets["astra"]["ASTRA_COLLECTION_NAME"],
        token=secrets["astra"]["ASTRA_DB_APPLICATION_TOKEN"],
        api_endpoint=secrets["astra"]["ASTRA_DB_API_ENDPOINT"],
        namespace=secrets["astra"]["ASTRA_DB_KEYSPACE"],
        collection_vector_service_options=VectorServiceOptions(
            provider=secrets["openai"]["OPENAI_PROVIDER"],
            model_name=secrets["openai"]["OPENAI_TEXT_EMBEDDING_MODEL"],
            authentication={"providerKey": secrets["astra"]["ASTRA_DB_API_KEY_NAME"]},
        ),
    )
    return secrets, vector_store

def render_references(docs):
    if docs:
        st.markdown("### References")
        for i, doc in enumerate(docs, start=1):
            title = doc.metadata.get("title", "").strip()
            url = doc.metadata.get("author", "").strip()
            if not title and url:
                parsed = urlparse(url)
                title = os.path.basename(parsed.path) or "Unknown Document"
            page = doc.metadata.get("page", "N/A")
            with st.expander(f"{i}. {title} (Page {page})"):
                st.markdown(f"[Link to Document]({url})")
                st.markdown(doc.page_content or "No content available.")

def render_chat_page():
    st.title("ClerkGPT Chat")
    st.markdown("Welcome to ClerkGPT! Ask your questions below.")
    menu()
    secrets, vector_store = get_secrets_and_vector_store()
    retriever = vector_store.as_retriever()

    system_prompt = (
        "You are a helpful and theologically-informed research assistant trained to answer questions using documents "
        "from the Presbyterian Church in America (PCA), including General Assembly minutes, presbytery reports, overtures, "
        "theological statements, and historical records. Your task is to provide clear, accurate, and well-reasoned answers "
        "grounded in the content of the documents provided in the context, and reflective of the PCA’s Reformed and confessional commitments."
    )
    chat = ChatOpenAI(
        temperature=0,
        openai_api_key=secrets['openai']["OPENAI_API_KEY"],
        model=secrets["openai"]["OPENAI_MODEL"],
    )
    custom_prompt = ChatPromptTemplate.from_messages([
        SystemMessagePromptTemplate.from_template(system_prompt),
        HumanMessagePromptTemplate.from_template("{context}\n\nQuestion: {question}")
    ])

    qa_chain = ConversationalRetrievalChain.from_llm(
        llm=chat,
        retriever=retriever,
        memory=st.session_state.memory,
        combine_docs_chain_kwargs={"prompt": custom_prompt},
        return_source_documents=True,
        output_key="answer"
    )

    # --- Display chat history ---
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant" and "results" in message:
                render_references(message["results"])

    # --- User input and response ---
    if prompt := st.chat_input("Ask me anything!"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        try:
            with st.spinner("Generating response..."):
                result = qa_chain({
                    "question": prompt,
                    "chat_history": st.session_state.memory.buffer
                })
                assistant_message = result["answer"]
                docs = result.get("source_documents", [])
        except Exception as e:
            assistant_message = f"Error generating response: {e}"
            docs = []
        st.session_state.messages.append({
            "role": "assistant",
            "content": assistant_message,
            "results": docs,
        })
        with st.chat_message("assistant"):
            st.markdown(assistant_message,)
            render_references(docs)

    # --- Optional: Reset conversation ---
    if st.button("Reset Conversation"):
        st.session_state.messages = []
        st.session_state.memory.clear()


# --- Run the chat page
if 'authenticated' in st.session_state and st.session_state['authenticated']:
    render_chat_page()