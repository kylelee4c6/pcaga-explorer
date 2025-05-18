import streamlit as st
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from langchain_astradb import AstraDBVectorStore
from astrapy.info import VectorServiceOptions
from menu import menu

system_prompt = (
    "You are a helpful research assistant trained to answer questions using documents from "
    "the Presbyterian Church in America (PCA), including General Assembly minutes, presbytery reports, "
    "theological statements, overtures, and historical documents. "
    "Provide clear, accurate, and well-reasoned answers that are grounded in the source materials. "
    "When appropriate, cite the specific document, section or page number your answer is based on. "
    "If the answer is not clearly available in the documents, say so directly and suggest how the user might "
    "refine their query or explore related topics. Your tone should be informative, respectful, and theologically aware, "
    "recognizing the Reformed and confessional context of the PCA."
)
# Keep track of the current page
if "current_page" not in st.session_state:
    st.session_state.current_page = "chat"
def render_chat_page():
    st.session_state.current_page = "chat"
    menu()

    # Load environment variables
    OPENAI_API_KEY = st.secrets['openai']["OPENAI_API_KEY"]
    MODEL_NAME = st.secrets["openai"]["OPENAI_MODEL"]
    OPENAI_PROVIDER = st.secrets["openai"]["OPENAI_PROVIDER"]
    OPENAI_TEXT_EMBEDDING_MODEL = st.secrets["openai"]["OPENAI_TEXT_EMBEDDING_MODEL"]

    ASTRA_DB_APPLICATION_TOKEN = st.secrets["astra"]["ASTRA_DB_APPLICATION_TOKEN"]
    ASTRA_DB_API_ENDPOINT = st.secrets["astra"]["ASTRA_DB_API_ENDPOINT"]
    ASTRA_DB_KEYSPACE = st.secrets["astra"]["ASTRA_DB_KEYSPACE"]
    ASTRA_DB_API_KEY_NAME = st.secrets["astra"]["ASTRA_DB_API_KEY_NAME"]
    ASTRA_COLLECTION_NAME = st.secrets["astra"]["ASTRA_COLLECTION_NAME"]

    # Vector store setup
    vectorize_options = VectorServiceOptions(
        provider=OPENAI_PROVIDER,
        model_name=OPENAI_TEXT_EMBEDDING_MODEL,
        authentication={"providerKey": ASTRA_DB_API_KEY_NAME},
    )
    vector_store = AstraDBVectorStore(
        collection_name=ASTRA_COLLECTION_NAME,
        token=ASTRA_DB_APPLICATION_TOKEN,
        api_endpoint=ASTRA_DB_API_ENDPOINT,
        namespace=ASTRA_DB_KEYSPACE,
        collection_vector_service_options=vectorize_options,
    )
    st.markdown("## Chat with ClerkGPT")
    # Initialize chat history
    if "messages" not in st.session_state:
        st.session_state.messages = []

    # Display chat messages from history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # React to user input
    if prompt := st.chat_input("Ask me anything!"):
        # Display user message
        st.chat_message("user").markdown(prompt)
        st.session_state.messages.append({"role": "user", "content": prompt})

        # Perform vector search for relevant documents
        try:
            results = vector_store.similarity_search(prompt, k=st.session_state.num_references)
            context = "\n".join([f"{res.page_content} Source: {res.metadata.get('title')} URL: {res.metadata.get('author', 'N/A')} Page Number: {res.metadata.get('page')}" for res in results])
            references = [
                {
                    "content": res.page_content,
                    "page": res.metadata.get("page", "N/A"),
                    "title": res.metadata.get("title") or "N/A",
                    "url": res.metadata.get("author", "N/A"),
                }
                for res in results
            ]
        except Exception as e:
            context = f"Error retrieving documents: {e}"
            references = []

        # Generate response using OpenAI via LangChain
        try:
            chat = ChatOpenAI(temperature=0, openai_api_key=OPENAI_API_KEY, model=MODEL_NAME)
            response = chat([
                SystemMessage(content=system_prompt),
                HumanMessage(content=f"Context: {context}\n\nQuestion: {prompt}")
            ])
            assistant_message = response.content
        except Exception as e:
            assistant_message = f"Error generating response: {e}"

        # Display assistant response
        with st.chat_message("assistant"):
            st.markdown(assistant_message)

            # Display references as accordions
            st.markdown("### References")
            for i, ref in enumerate(references, start=1):
                
                with st.expander(f"Doc. {i}: (Title: {ref['title']}, Page {ref['page']}, URL: {ref['url']})"):
                    # Show URL
                    st.markdown(f"[Link to Document]({ref['url']})")
                    st.markdown("**Content:**")
                    st.markdown(ref["content"])
        st.session_state.messages.append({"role": "assistant", "content": assistant_message})


render_chat_page()