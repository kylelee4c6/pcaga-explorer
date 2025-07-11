import streamlit as st
import os
from langchain_openai import ChatOpenAI
from langchain_astradb import AstraDBVectorStore
from astrapy.info import VectorServiceOptions
from urllib.parse import urlparse

from langchain.chains import create_history_aware_retriever, create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage

from astrapy import DataAPIClient
from menu import menu
import uuid
from datetime import datetime
import time
if "toast_shown" not in st.session_state:
    st.session_state.toast_shown = False
if not st.session_state.toast_shown:
    st.toast(f"From Kyle: Hi {st.user.get('name')}. For research purposes, your queries may be recorded and analyzed. I appreciate your understanding as I learn to figure out how to make this application more useful. I may contact you to learn more about your use case to apply more advanced features. ", icon="🔎")
    st.session_state.toast_shown = True
    time.sleep(10)
if "messages" not in st.session_state:
    st.session_state.messages = []

@st.cache_resource(show_spinner=False)
def get_vector_store():
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
    return vector_store

@st.cache_resource(show_spinner=False)
def get_query_store():
    secrets = st.secrets
    client = DataAPIClient(secrets['astra']['ASTRA_COLLECTION_USERNAME_TOKEN'])
    db = client.get_database_by_api_endpoint(secrets['astra']['ASTRA_DB_API_ENDPOINT'])
    table = db.get_table(secrets['astra']['ASTRA_QUERY_DB'])
    return table
    
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
                st.markdown(f"[Link to Document]({url})\n")
                st.markdown(doc.page_content or "No content available.")

def render_chat_page():
    menu()
    
    if 'session_id' not in st.session_state:
        st.session_state.session_id = str(uuid.uuid4())
    if "current_page" not in st.session_state:
        st.session_state.current_page = "chat"
    st.title("ClerkGPT Chat")
    st.markdown("Welcome to ClerkGPT! Ask your questions below.")

    vector_store = get_vector_store()
    retriever = vector_store.as_retriever(
        search_type="similarity_score_threshold",
        search_kwargs={"score_threshold": 0.4, "k": 15}
    )

    query_tracker = get_query_store()

    chat = ChatOpenAI(
        temperature=0,
        openai_api_key=st.secrets['openai']["OPENAI_API_KEY"],
        model=st.secrets["openai"]["OPENAI_MODEL"],
    )

    # Create history-aware retriever
    contextualize_q_system_prompt = (
        "Given a chat history and the latest user question "
        "which might reference context in the chat history, "
        "formulate a standalone question which can be understood "
        "without the chat history. Do NOT answer the question, "
        "just reformulate it if needed and otherwise return it as is."
    )
    
    contextualize_q_prompt = ChatPromptTemplate.from_messages([
        ("system", contextualize_q_system_prompt),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ])
    
    history_aware_retriever = create_history_aware_retriever(
        chat, retriever, contextualize_q_prompt
    )

    # Create the question-answering chain
    system_prompt = (
        "You are a helpful and theologically-informed research assistant trained to answer questions using documents "
        "from the Presbyterian Church in America (PCA), including General Assembly minutes, presbytery reports, overtures, "
        "theological statements, and historical records. Your task is to provide clear, accurate, and well-reasoned answers "
        "grounded in the content of the documents provided in the context, and reflective of the PCA's Reformed and confessional commitments. "
        "You should always cite the sources of your information where it's relevant using the documents provided. "
        "Always remember you do not represent the PCA. Some useful acronyms: BCO is Book of Church Order, SJC is Standing Judicial Commission. Ensure responses are in English."
        "\n\n"
        "{context}"
    )
    
    qa_prompt = ChatPromptTemplate.from_messages([
        ("system", system_prompt),
        MessagesPlaceholder("chat_history"),
        ("human", "{input}"),
    ])
    
    question_answer_chain = create_stuff_documents_chain(chat, qa_prompt)
    
    # Create the final retrieval chain
    qa_chain = create_retrieval_chain(history_aware_retriever, question_answer_chain)

    # Helper function to convert messages to chat history format
    def get_chat_history():
        """Convert session messages to chat history format for the new chain."""
        chat_history = []
        for message in st.session_state.messages:
            if message["role"] == "user":
                chat_history.append(HumanMessage(content=message["content"]))
            elif message["role"] == "assistant":
                chat_history.append(AIMessage(content=message["content"]))
        return chat_history

    # Display chat history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            if message["role"] == "assistant" and "results" in message:
                render_references(message["results"])

    # User input and response
    if prompt := st.chat_input("Ask me anything!"):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Get chat history for the chain
        chat_history = get_chat_history()
        
        # Generate response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                try:
                    # Invoke the new chain
                    result = qa_chain.invoke({
                        "input": prompt,
                        "chat_history": chat_history
                    })
                    
                    # Extract answer and source documents
                    answer = result["answer"]
                    source_docs = result.get("context", [])
                    
                    # Display the answer
                    st.markdown(answer)
                    
                    # Add assistant message to chat history
                    message_data = {
                        "role": "assistant", 
                        "content": answer,
                        "results": source_docs
                    }
                    st.session_state.messages.append(message_data)
                    
                    # Display references if available
                    if source_docs:
                        render_references(source_docs)
                        
                    # Track query - Fixed method call
                    if query_tracker:
                        try:
                            # Insert the query record into the database
                            query_data = {
                                "query_id":str(uuid.uuid4()),
                                "session": st.session_state.session_id,
                                "user": st.user.get('email'),
                                "query": prompt,
                                "timestamp": datetime.now().isoformat(),
                            }
                            query_tracker.insert_one(query_data)
                        except Exception as query_error:
                            st.warning(f"Failed to track query: {str(query_error)}")
                        
                except Exception as e:
                    st.error(f"An error occurred: {str(e)}")
                    st.session_state.messages.append({
                        "role": "assistant", 
                        "content": f"I apologize, but I encountered an error: {str(e)}"
                    })

if 'authenticated' in st.session_state and st.session_state['authenticated']:
    render_chat_page()