### Task Overview
Utkrusht operates a containerized RAG system where a FastAPI application retrieves documentation context from a ChromaDB vector store. Currently, the system relies on ChromaDB’s default embedding function, meaning no explicit embedding model is configured in the app or during initialization. A new requirement mandates using a specific embedding model for improved retrieval quality. However, because past data was embedded using the default model, the existing vectors are incompatible with the new query embeddings.

### Objectives
- Introduce a consistent embedding strategy across the RAG pipeline by configuring the system to use the specified sentence-transformers/all-mpnet-base-v2 model instead of ChromaDB’s default behavior.
- Develop a safe and repeatable process to refresh all existing vector data so that stored embeddings align with the updated model.
- Ensure the revised embedding workflow operates correctly within the Dockerized environment.
- Validate that retrieval behavior reflects the updated embedding model by exercising a few representative queries and confirming that responses align more closely with the intent of the input.

## Application Access

- RAG API (FastAPI application):
  - Base URL: `http://<DROPLET_IP>:8000`
  - `GET /health` — Health check endpoint reporting the status of the RAG app and its connection to ChromaDB/data.
  - `POST /query` — Submit a query to the RAG system. The body should be JSON of the form:
    ```json
    {
      "query": "How does Utkrusht pre-populate skill assessments?",
      "top_k": 3
    }
    ```
  - `GET /docs` — FastAPI's Swagger UI for exploring and testing the API.

- ChromaDB HTTP API (for debugging and validation):
  - Heartbeat: `GET http://<DROPLET_IP>:8001/api/v1/heartbeat` — confirm ChromaDB is running.
  - Collections: `GET http://<DROPLET_IP>:8001/api/v1/collections` — list existing collections and verify that the Utkrusht documentation collection is present.

### How to Verify
- Start the full Docker stack and confirm ChromaDB, the initialization process, and the RAG app come up cleanly.
- Connect to ChromaDB to confirm the vector store is reachable and contains expected data.
- Execute your re-embedding script and verify that documents are successfully updated using the new model.
- Send a few test queries to the RAG API and observe clearer, more relevant document retrieval compared to the default embedding behavior.
- Optionally inspect similarity scores or document ordering to confirm meaningful improvements.

### Helpful Tips
- Inspect how the current RAG app interacts with ChromaDB; since no model is explicitly set, ChromaDB has been embedding documents using its built-in default.
- When switching to a custom embedding model, ensure both query-time embeddings and stored vector embeddings are generated using the same model.
- A re-embedding script is often the simplest way to migrate existing documents: fetch them, update their embeddings, and write them back.
- Leverage Docker networking to run and test the new embedding pipeline without modifying how services discover each other.
- Try a few reference queries before and after your changes to observe the improvements in retrieval quality.
