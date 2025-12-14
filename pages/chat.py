import streamlit as st
import os
from langchain_openai import ChatOpenAI
from langchain_astradb import AstraDBVectorStore
from astrapy.info import VectorServiceOptions
from urllib.parse import urlparse

from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage
from langchain_core.output_parsers import JsonOutputParser
from langgraph.graph import StateGraph, END
from typing import TypedDict, List, Optional
from pydantic import BaseModel, Field

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
if "current_page" not in st.session_state:
    st.session_state.current_page = "chat"
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

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

class GradeDocuments(BaseModel):
    score: str = Field(description="Binary score 'yes' or 'no' for document relevance")
    relevance_score: float = Field(description="Relevance score from 0.0 to 1.0")
    reasoning: str = Field(description="Brief explanation of the relevance decision")

class QueryRouter(BaseModel):
    needs_retrieval: bool = Field(description="Whether the query needs document retrieval")
    query_type: str = Field(description="Type of query: pca_specific, general_theology, greeting, meta")
    reasoning: str = Field(description="Brief explanation of routing decision")

class HallucinationCheck(BaseModel):
    is_grounded: bool = Field(description="Whether the response is grounded in provided documents")
    confidence: float = Field(description="Confidence score from 0.0 to 1.0")
    issues: str = Field(description="Any hallucination concerns identified")

class GraphState(TypedDict, total=False):
    question: str
    generation: str
    documents: List
    chat_history: List
    routing: dict
    hallucination_check: dict

def grade_and_rank_documents(state: GraphState, llm) -> GraphState:
    question = state["question"]
    documents = state["documents"]
    
    grade_prompt = ChatPromptTemplate.from_template("""
    You are a document relevance grader for Presbyterian Church in America (PCA) queries.
    
    Document: {document}
    Question: {question}
    
    Evaluate this document's relevance to the question:
    1. Does it contain information directly related to the question?
    2. How specific and useful is the information?
    3. Rate relevance from 0.0 (irrelevant) to 1.0 (highly relevant)
    
    Provide: binary score ('yes'/'no'), relevance_score (0.0-1.0), and brief reasoning.
    """)
    
    grader = grade_prompt | llm.with_structured_output(GradeDocuments)
    
    scored_docs = []
    for doc in documents:
        grade = grader.invoke({"question": question, "document": doc.page_content})
        if grade.score == "yes" and grade.relevance_score > 0.3:
            scored_docs.append({
                "doc": doc,
                "score": grade.relevance_score,
                "reasoning": grade.reasoning
            })
    
    # Rank by relevance score
    scored_docs.sort(key=lambda x: x["score"], reverse=True)
    
    # Apply diversity filtering
    filtered_docs = apply_diversity_filter(scored_docs, question)
    
    return {"question": question, "documents": filtered_docs, "chat_history": state["chat_history"]}

def apply_diversity_filter(scored_docs, question, max_docs=8, similarity_threshold=0.7):
    if not scored_docs:
        return []
    
    diverse_docs = [scored_docs[0]["doc"]]  # Always include top doc
    
    for candidate in scored_docs[1:]:
        if len(diverse_docs) >= max_docs:
            break
            
        # Check content similarity with already selected docs
        is_diverse = True
        candidate_content = candidate["doc"].page_content.lower()
        
        for selected_doc in diverse_docs:
            selected_content = selected_doc.page_content.lower()
            
            # Simple diversity check based on content overlap
            common_words = set(candidate_content.split()) & set(selected_content.split())
            total_words = len(set(candidate_content.split()) | set(selected_content.split()))
            
            if total_words > 0:
                similarity = len(common_words) / total_words
                if similarity > similarity_threshold:
                    is_diverse = False
                    break
        
        if is_diverse:
            diverse_docs.append(candidate["doc"])
    
    return diverse_docs

def rewrite_query(state: GraphState, llm) -> GraphState:
    question = state["question"]
    chat_history = state["chat_history"]
    
    rewrite_prompt = ChatPromptTemplate.from_template("""
    You are a question rewriter. Analyze the user question and rewrite it to be more specific for retrieving relevant PCA documents.
    
    Original question: {question}
    Chat history: {chat_history}
    
    Improve the question by:
    1. Adding relevant PCA/Presbyterian context if missing
    2. Making terminology more specific (e.g., "BCO" for Book of Church Order)  
    3. Clarifying ambiguous references using chat history
    
    Return only the rewritten question without any additional text.
    """)
    
    rewriter = rewrite_prompt | llm
    rewritten_question = rewriter.invoke({"question": question, "chat_history": chat_history})
    
    return {"question": rewritten_question.content, "documents": state["documents"], "chat_history": chat_history}

def route_query(state: GraphState, llm) -> GraphState:
    question = state["question"]
    
    router_prompt = ChatPromptTemplate.from_template("""
    You are a query router for a Presbyterian Church in America (PCA) knowledge system.
    
    Analyze this user query: "{question}"
    
    IMPORTANT: Answer directly WITHOUT document retrieval for:
    - Simple greetings: "hello", "hi", "hey", "thanks", "goodbye", "thank you"
    - Casual conversation: "how are you", "what's up", "good morning"
    - Meta questions: about the system, how it works, what it can do
    - General theology that doesn't need PCA-specific documents
    - Off-topic or inappropriate questions
    
    Use document retrieval ONLY for:
    - Specific PCA policies, procedures, or rulings
    - Book of Church Order (BCO) questions
    - Standing Judicial Commission (SJC) cases or decisions
    - General Assembly minutes, reports, or overtures
    - Presbytery-specific information or procedures
    - Historical PCA documents or church decisions
    - PCA confessional positions or theological stances
    - Westminster Confession of Faith questions
    
    Respond with JSON containing:
    - needs_retrieval: false for greetings/general, true for PCA-specific
    - query_type: "greeting", "general_theology", "pca_specific", or "meta"
    - reasoning: brief explanation of your decision
    """)
    
    router = router_prompt | llm.with_structured_output(QueryRouter)
    result = router.invoke({"question": question})
    
    state["routing"] = {
        "needs_retrieval": result.needs_retrieval,
        "query_type": result.query_type,
        "reasoning": result.reasoning
    }
    
    return state

def check_hallucination(state: GraphState, llm) -> GraphState:
    question = state["question"]
    generation = state["generation"]
    documents = state["documents"]
    
    if not documents:
        # If no documents, can't check grounding
        state["hallucination_check"] = {
            "is_grounded": True,  # Assume general knowledge is acceptable
            "confidence": 0.7,
            "issues": "No source documents available for grounding check"
        }
        return state
    
    context = "\n\n".join([doc.page_content for doc in documents])
    
    hallucination_prompt = ChatPromptTemplate.from_template("""
    You are a fact-checker analyzing whether an AI response is properly grounded in the provided source documents.
    
    Question: {question}
    AI Response: {response}
    Source Documents: {context}
    
    Analyze if the AI response:
    1. Makes claims supported by the source documents
    2. Avoids adding information not in the sources
    3. Properly represents the source content
    4. Avoids speculation beyond what's documented
    
    Rate grounding confidence from 0.0 (completely hallucinated) to 1.0 (fully grounded).
    Identify any specific hallucination concerns.
    
    Provide: is_grounded (boolean), confidence (0.0-1.0), and issues (string).
    """)
    
    checker = hallucination_prompt | llm.with_structured_output(HallucinationCheck)
    result = checker.invoke({
        "question": question,
        "response": generation,
        "context": context
    })
    
    state["hallucination_check"] = {
        "is_grounded": result.is_grounded,
        "confidence": result.confidence,
        "issues": result.issues
    }
    
    return state

@st.cache_resource(show_spinner=False)
def create_agentic_rag_chain(_chat_llm, _retriever):
    def retrieve_docs(state: GraphState) -> GraphState:
        question = state["question"]
        docs = _retriever.invoke(question)
        return {"question": question, "documents": docs, "chat_history": state["chat_history"]}
    
    def generate_answer(state: GraphState) -> GraphState:
        question = state["question"]
        documents = state["documents"]
        chat_history = state["chat_history"]
        
        if not documents:
            prompt = ChatPromptTemplate.from_template("""
            You are a helpful assistant for Presbyterian Church in America (PCA) questions.
            
            Question: {question}
            Chat History: {chat_history}
            
            No relevant documents were found in the knowledge base. Please provide a helpful response based on your general knowledge of Presbyterian theology and practice, but clearly indicate that this response is not based on specific PCA documents.
            """)
            chain = prompt | _chat_llm
            response = chain.invoke({
                "question": question,
                "chat_history": chat_history
            })
        else:
            context = "\n\n".join([doc.page_content for doc in documents])
            prompt = ChatPromptTemplate.from_template("""
            You are a helpful and theologically-informed research assistant for the Presbyterian Church in America (PCA).
            
            Context from PCA documents: {context}
            Question: {question}
            Chat History: {chat_history}
            
            Provide a clear, accurate answer based on the context provided. Always cite sources when relevant.
            """)
            chain = prompt | _chat_llm
            response = chain.invoke({
                "question": question, 
                "context": context,
                "chat_history": chat_history
            })
        
        return {"question": question, "documents": documents, "generation": response.content, "chat_history": chat_history}
    
    def route_decision(state: GraphState) -> str:
        routing = state.get("routing", {})
        needs_retrieval = routing.get("needs_retrieval", False)
        
        # Debug logging
        print(f"Routing decision: needs_retrieval={needs_retrieval}, query_type={routing.get('query_type', 'unknown')}")
        
        if needs_retrieval:
            return "retrieve"
        else:
            return "generate_direct"
    
    def decide_to_generate(state: GraphState) -> str:
        documents = state["documents"]
        if documents:
            return "generate"
        else:
            return "rewrite"
    
    def generate_direct_answer(state: GraphState) -> GraphState:
        question = state["question"]
        chat_history = state["chat_history"]
        query_type = state.get("routing", {}).get("query_type", "general")
        
        if query_type == "greeting":
            direct_prompt = ChatPromptTemplate.from_template("""
            You are ClerkGPT, a helpful assistant for Presbyterian Church in America (PCA) questions.
            
            The user said: {question}
            
            Respond warmly and briefly to this greeting. Offer to help with PCA-related questions like church governance, the Book of Church Order, General Assembly matters, or theological questions.
            
            Keep your response friendly and concise (2-3 sentences maximum).
            """)
        else:
            direct_prompt = ChatPromptTemplate.from_template("""
            You are ClerkGPT, a helpful assistant for Presbyterian Church in America (PCA) questions.
            
            Question: {question}
            Chat History: {chat_history}
            
            This question doesn't require searching PCA documents. Provide a helpful response based on general knowledge, but note that for specific PCA policies or procedures, users should ask more detailed questions.
            """)
        
        chain = direct_prompt | _chat_llm
        response = chain.invoke({
            "question": question,
            "chat_history": chat_history
        })
        
        return {"question": question, "documents": [], "generation": response.content, "chat_history": chat_history, "routing": state.get("routing", {}), "hallucination_check": {}}
    
    workflow = StateGraph(GraphState)
    
    # Add all nodes
    workflow.add_node("route", lambda state: route_query(state, _chat_llm))
    workflow.add_node("retrieve", retrieve_docs)
    workflow.add_node("grade_documents", lambda state: grade_and_rank_documents(state, _chat_llm))
    workflow.add_node("generate", generate_answer)
    workflow.add_node("generate_direct", generate_direct_answer)
    workflow.add_node("rewrite", lambda state: rewrite_query(state, _chat_llm))
    workflow.add_node("check_hallucination", lambda state: check_hallucination(state, _chat_llm))
    
    # Set entry point and edges
    workflow.set_entry_point("route")
    workflow.add_conditional_edges(
        "route",
        route_decision,
        {
            "retrieve": "retrieve",
            "generate_direct": "generate_direct"
        }
    )
    workflow.add_edge("retrieve", "grade_documents")
    workflow.add_conditional_edges(
        "grade_documents",
        decide_to_generate,
        {
            "rewrite": "rewrite",
            "generate": "generate",
        },
    )
    workflow.add_edge("rewrite", "retrieve")
    workflow.add_edge("generate", "check_hallucination")
    workflow.add_edge("generate_direct", "check_hallucination")
    workflow.add_edge("check_hallucination", END)
    
    return workflow.compile()

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

    # Set session states
    st.session_state.current_page = "chat"
    st.session_state.session_id = str(uuid.uuid4())
    menu()
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

    # Create agentic RAG chain
    agentic_rag_chain = create_agentic_rag_chain(chat, retriever)

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
                    # Invoke the agentic RAG chain
                    result = agentic_rag_chain.invoke({
                        "question": prompt,
                        "chat_history": chat_history,
                        "documents": [],
                        "generation": "",
                        "routing": {},
                        "hallucination_check": {}
                    })
                    
                    # Extract answer and source documents
                    answer = result["generation"]
                    source_docs = result.get("documents", [])
                    hallucination_check = result.get("hallucination_check", {})
                    
                    # Display the answer
                    st.markdown(answer)
                    
                    # Show quality indicators if confidence is low
                    if hallucination_check.get("confidence", 1.0) < 0.6:
                        st.warning(f"⚠️ Response confidence: {hallucination_check.get('confidence', 0):.1%} - Please verify information")
                    
                    if not hallucination_check.get("is_grounded", True) and source_docs:
                        st.error("⚠️ This response may contain information not fully supported by the source documents")
                    
                    # Add assistant message to chat history
                    message_data = {
                        "role": "assistant", 
                        "content": answer,
                        "results": source_docs,
                        "quality_check": hallucination_check
                    }
                    st.session_state.messages.append(message_data)
                    
                    # Display references if available
                    if source_docs:
                        render_references(source_docs)
                        st.caption(f"📊 Showing {len(source_docs)} most relevant and diverse documents")
                        
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