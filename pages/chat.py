import streamlit as st
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage
from langchain_astradb import AstraDBVectorStore
from astrapy.info import VectorServiceOptions
from menu import menu

from pydantic import BaseModel, Field
from typing import List
from langchain.output_parsers import PydanticOutputParser

if "messages" not in st.session_state:
    st.session_state.messages = []
if "references" not in st.session_state:
    st.session_state.references = []

# Define Pydantic models for structured response
class Source(BaseModel):
    document_id: str = Field(..., description="Unique identifier for the source document derived from the id field in the metadata of the Document.")

class AnswerWithSources(BaseModel):
    answer: str = Field(..., description="The assistant's answer to the user question formatted as a markdown string.")
    sources: List[Source] = Field(
        default_factory=list, description="List of sources used for the answer that are relevant."
    )

system_prompt = (
    "You are a helpful and theologically-informed research assistant trained to answer questions using documents "
    "from the Presbyterian Church in America (PCA), including General Assembly minutes, presbytery reports, overtures, "
    "theological statements, and historical records. Your task is to provide clear, accurate, and well-reasoned answers "
    "grounded in the content of the documents provided in the context, and reflective of the PCA’s Reformed and confessional commitments.\n\n"

    "You must return a JSON object that conforms to the following structure:\n"
    "1. 'answer': a complete, markdown-formatted response to the user's question.\n"
    "2. 'sources': a list of objects, each with a single field 'document_id', representing the documents that were explicitly used in the answer.\n\n"

    "**Important Instructions:**\n"
    "- Every document listed in the 'sources' array must be directly cited, quoted, paraphrased, or meaningfully referenced in the 'answer' without the document ID.\n"
    "- Do not include any document in the 'sources' list unless its content was actually used to form the answer.\n"
    "- Each 'document_id' must exactly match an ID provided in the metadata of the context (from the 'id' field of the Document object).\n"
    "- If your answer uses text or ideas from a document, you must include its 'document_id' in the 'sources' list.\n"
    "- Do not fabricate or infer content that is not supported by the provided context.\n\n"

    "If no relevant or adequate answer can be found in the documents, say so directly in the 'answer', and offer constructive suggestions "
    "for how the user might refine their question or explore related topics.\n\n"

    "Your tone should be informative, respectful, and pastorally aware, helping users understand the PCA’s theology, polity, and historical context.\n\n"

    "**Return only valid JSON conforming to this schema. Do not include fields not defined in the model. The 'answer' must align directly with the documents listed in 'sources'.**"
)
# Keep track of the current page
if "current_page" not in st.session_state:
    st.session_state.current_page = "chat"
def get_matched_result(document_id, results):
    """Find the matching result from results based on document_id."""
    return next((res for res in results if res.id == document_id), None)
def render_chat_page():
    menu()

    st.markdown("## Chat with ClerkGPT")

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

    # Instantiate parser
    parser = PydanticOutputParser(pydantic_object=AnswerWithSources)

    # Vector store setup
    vector_store = AstraDBVectorStore(
        collection_name=ASTRA_COLLECTION_NAME,
        token=ASTRA_DB_APPLICATION_TOKEN,
        api_endpoint=ASTRA_DB_API_ENDPOINT,
        namespace=ASTRA_DB_KEYSPACE,
        collection_vector_service_options=VectorServiceOptions(
            provider=OPENAI_PROVIDER,
            model_name=OPENAI_TEXT_EMBEDDING_MODEL,
            authentication={"providerKey": ASTRA_DB_API_KEY_NAME},
        ),
    )
    # Display existing chat history with references
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
            
            # Display references for assistant messages
            if message["role"] == "assistant" and "references" in message and "results" in message:
                json_sources = message["references"]
                results = message["results"]
                # Show citations
                if json_sources:
                    st.markdown("### References")
                    for i, ref in enumerate(json_sources, start=1):
                        # Match the document_id from json_sources with the id in results
                        matched_result = get_matched_result(ref.document_id, results)
                        if matched_result:
                            with st.expander(f"{i}. {matched_result.metadata.get('title', 'Unknown Title')} (Page {matched_result.metadata.get('page', 'N/A')})"):
                                st.markdown(f"[Link to Document]({matched_result.metadata.get('author', 'N/A')})")
                                st.markdown(matched_result.page_content or "No content available.")

    # Get new user input
    if prompt := st.chat_input("Ask me anything!"):
        # Save and show user message
        st.session_state.messages.append({"role": "user", "content": prompt})
        st.chat_message("user").markdown(prompt)

        # Get relevant docs
        try:
            with st.spinner("Retrieving relevant documents..."):
                results = vector_store.similarity_search(query=prompt, k=20, score_threshold=0.6)

            context = "\n".join(
                f"{res.page_content} Source: {res.metadata.get('title')} URL: {res.metadata.get('author','N/A')} Page: {res.metadata.get('page')}, Document id:{res.id}"
                for res in results
            )
        except Exception as e:
            results = []
            context = f"Error retrieving docs: {e}"
            
        # Get assistant answer
        try:
            chat = ChatOpenAI(
                temperature=0,
                openai_api_key=OPENAI_API_KEY,
                model=MODEL_NAME,
            )
            with st.spinner("Generating response..."):
                response = chat([
                    SystemMessage(content=f"{system_prompt}\n\n{parser.get_format_instructions()}"),
                    HumanMessage(content=f"Context:\n{context}\n\nQuestion:\n{prompt}"),
                ])
            parsed: AnswerWithSources = parser.parse(response.content)
            assistant_message = parsed.answer
            json_sources = parsed.sources

            
        except Exception as e:
            assistant_message = f"Error generating response: {e}"
            json_sources = []

        # Save new message with references
        st.session_state.messages.append({
            "role": "assistant",
            "content": assistant_message,
            "references": json_sources,  # Embed references directly in the message
            "results": results  # Store results for citation matching
        })

        # Show assistant's reply
        with st.chat_message("assistant"):
            st.markdown(assistant_message)

            # Show citations
            if json_sources:
                st.markdown("### References")
                for i, ref in enumerate(json_sources, start=1):
                    # Match the document_id from json_sources with the id in results
                    matched_result = get_matched_result(ref.document_id, results)
                    if matched_result:
                        with st.expander(f"{i}. {matched_result.metadata.get('title', 'Unknown Title')} (Page {matched_result.metadata.get('page', 'N/A')})"):
                            st.markdown(f"[Link to Document]({matched_result.metadata.get('author', 'N/A')})")
                            st.markdown(matched_result.page_content or "No content available.")
# Run the app
if 'authenticated' in st.session_state and st.session_state['authenticated']:
    render_chat_page()
