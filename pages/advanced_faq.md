### ⚙️ Advanced FAQ (For Technical Users)

#### **What models are used for embedding and generation?**

* **Embedding**: Document chunks are embedded using OpenAI’s `text-embedding-3-large` model.
* **Generation**: The application uses **OpenAI’s gpt-4.1-mini** model for generating responses based on retrieved context. Model selection can be swapped via environment configuration if needed.

#### **Where are the documents stored?**

* Documents and their corresponding embeddings are stored in **AstraDB Serverless**, which provides a scalable and cost-effective NoSQL database solution powered by Apache Cassandra.
* AstraDB is queried using the `vectordb` interface for vector similarity search based on cosine distance.

#### **How does retrieval work?**

* The system performs similarity search over chunked document embeddings. Retrieved chunks are ranked and concatenated into a prompt window.
* Optional metadata filtering (e.g. by document type or year) can be implemented to improve precision.

#### **What chunking strategy is used?**

* Documents are split into overlapping text chunks using a recursive character/text splitter with a fixed max token size (e.g. 1024 tokens) and slight overlap (e.g. 256) to preserve context across chunks.
* Chunks are indexed with metadata such as document title, source URL.

#### **Is this a closed system or extensible?**

* The system is designed to be **extensible**:

  * You can plug in different LLMs via OpenAI, Azure, or open-source endpoints (like vLLM) if you fork the API.
  * Embeddings and vector store backends can be swapped (e.g., for Weaviate, Pinecone, Qdrant).

#### **Is there any citation handling?**

* Responses include the most relevant document sources used to generate the answer. Each chunk is tied to metadata that includes source filenames and urls, which can be displayed alongside the answer.

#### **How is prompt construction handled?**

* Prompt templates follow a basic structure: system instruction + user question + retrieved context. The context is formatted for readability (e.g., section headers, block quotes).
* Guardrails or few-shot examples can be added to the system prompt to shape the tone or structure of responses.

#### **What are the known limitations?**

* **Hallucination risk** still exists, especially when the retrieved chunks are marginally relevant or ambiguous.
* **Latency** depends on OpenAI API calls and AstraDB query time, which can vary with load.
* **Scope** is limited to documents preprocessed and embedded into the vector store. Anything outside of that won't be accessible to the model.

#### **How is the application deployed?**

* The app is built with **Streamlit**, making it deployable to platforms like Streamlit Cloud, Hugging Face Spaces, or any Python-friendly cloud VM/container.
* Environment variables control keys, endpoints, and model settings for flexible deployment.