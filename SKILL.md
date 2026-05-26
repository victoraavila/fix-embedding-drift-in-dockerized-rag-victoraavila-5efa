# Skill: Fix Embedding Drift in Dockerized RAG

## Project Overview

A Dockerized RAG (Retrieval-Augmented Generation) system for querying Utkrusht internal documentation. The system uses **FastAPI** as the application layer and **ChromaDB** as the vector store, all orchestrated via Docker Compose.

**Core Problem:** The system currently relies on ChromaDB's **default embedding function** (no explicit model configured). The requirement is to switch to `sentence-transformers/all-mpnet-base-v2`, but existing vectors were embedded with the default model, causing **embedding drift** — stored vectors are incompatible with new query embeddings.

---

## Architecture

```
┌─────────────┐  ┌──────────────┐  ┌─────────────┐
│  rag-app    │  │ chroma-init   │  │  chromadb   │
│ (FastAPI)   │  │ (load_data)  │  │  (vector DB)│
│ :8000       │  │ (one-shot)   │  │ :8000       │
└──────┬──────┘  └──────┬───────┘  └──────┬──────┘
       │                │                  │
       └────────────────┴──────────────────┘
              Docker network (bridge)
```

- **chromadb** (container): Runs ChromaDB v0.5.23 on port 8000 (mapped to host 8001). Persistent data via `chroma_data` volume.
- **chroma-init** (one-shot container): Loads `sample_data.json` (25 docs) into ChromaDB on startup. Idempotent — skips if data already exists.
- **rag-app** (FastAPI container): Serves the RAG API on host port 8000. Connects to ChromaDB via Docker network.

---

## File Map

| File | Purpose |
|---|---|
| `src/main.py` | FastAPI app with `/health` and `/query` endpoints |
| `src/config.py` | Config from env vars: `CHROMA_HOST`, `CHROMA_PORT`, `COLLECTION_NAME` |
| `src/models.py` | Pydantic models: `QueryRequest`, `QueryResponse`, `ContextItem` |
| `src/rag_pipeline.py` | `retrieve_context()` queries ChromaDB; `generate_answer()` stitches snippets (no LLM) |
| `src/vector_store.py` | ChromaDB client logic: `get_collection()`, `query_collection()`, `ensure_collection_has_data()` |
| `init-scripts/load_data.py` | Loads `sample_data.json` into ChromaDB (idempotent) |
| `init-scripts/sample_data.json` | 25 Utkrusht documentation chunks |
| `docker-compose.yml` | Orchestrates 3 services: chromadb, chroma-init, rag-app |
| `Dockerfile` | Builds the rag-app image (Python 3.11-slim, uvicorn) |
| `Dockerfile.init` | Builds the chroma-init image (minimal deps) |
| `requirements.txt` | Python deps: chromadb, fastapi, uvicorn, pydantic, requests, python-dotenv |
| `run.sh` | Starts stack, waits for init, health check, sample query |
| `kill.sh` | Tears down stack, removes volumes/images |
| `.env.example` | Env var template (CHROMA_HOST, CHROMA_PORT) |

---

## API Endpoints

- `GET /health` — Returns `{"status": "ok"}` or `{"status": "degraded"}` or 503
- `POST /query` — Body: `{"query": "...", "top_k": 3}` → `{"query": "...", "answer": "...", "contexts": [...]}`
- `GET /docs` — Swagger UI

---

## Key Code Details

### `src/vector_store.py`
- `get_collection()` uses `client.get_or_create_collection(name=COLLECTION_NAME)` — **no embedding function specified**, so ChromaDB uses its default (`all-MiniLM-L6-v2` in chromadb 0.5.x).
- `query_collection()` calls `coll.query(query_texts=[...], n_results=top_k)` — relies on ChromaDB's default embedding.

### `init-scripts/load_data.py`
- `collection.add(ids, documents, metadatas)` — also uses **no explicit embedding function**.
- Idempotent: skips loading if `collection.count() > 0`.

### `src/config.py`
- Defaults: `CHROMA_HOST=chromadb`, `CHROMA_PORT=8000`, `COLLECTION_NAME=utkrusht_docs`
- `CHROMA_RETRY_ATTEMPTS=5`, `CHROMA_RETRY_SLEEP_SECONDS=2`

### `docker-compose.yml`
- ChromaDB exposed on host port **8001** (container 8000)
- RAG app exposed on host port **8000** (container 8000)
- `src/` mounted read-only into rag-app container
- `chroma_data` named volume for persistence

---

## Task Objectives

1. **Configure explicit embedding model** `sentence-transformers/all-mpnet-base-v2` across the entire pipeline (init script + RAG app).
2. **Re-embed existing data**: Create a migration/re-embedding process to refresh all stored vectors with the new model so they're compatible with query-time embeddings.
3. **Ensure Docker compatibility**: The new embedding model must work inside the Docker containers (model download, cache, etc.).
4. **Validate retrieval**: Test queries should return more relevant results after the fix.

---

## Implementation Notes

### Embedding Function Configuration
- ChromaDB's `get_or_create_collection()` and `HttpClient` support a custom `embedding_function` parameter.
- Use `sentence_transformers.SentenceTransformer("sentence-transformers/all-mpnet-base-v2")` wrapped via `chromadb.utils.embedding_functions.SentenceTransformerEmbeddingFunction`.
- Must be applied in **both** `init-scripts/load_data.py` and `src/vector_store.py`.

### Re-embedding Strategy
- Since `collection.add()` with no explicit embedding function used the default model, existing vectors must be refreshed.
- Options:
  1. **Delete and re-add**: Fetch all documents/metadatas from the collection, delete the collection, recreate with the new embedding function, and re-add.
  2. **Update embeddings**: Use `collection.update()` to replace embeddings for existing document IDs with newly computed ones.
  3. **Wipe volume**: Remove the `chroma_data` volume and re-run init (cleanest for dev).
- For production safety, approach (1) or (2) is preferred. For this dev scenario, approach (3) (killing and rebuilding) may be simplest.

### Docker Considerations
- `sentence-transformers` will download the model (~420MB) on first use. Plan for:
  - Added `sentence-transformers` in `requirements.txt` / `Dockerfile` / `Dockerfile.init`.
  - Model caching in a Docker volume to avoid re-downloads on restarts.
  - Increased container startup time on first run.
- The `chromadb` package pulls in `sentence-transformers` as an optional dependency; may need explicit install.

### Testing
- `run.sh` sends a sample query: `{"query": "What is a proof-of-skills marketplace?", "top_k": 3}`
- Also test via: `curl http://<DROPLET_IP>:8000/query -X POST -H "Content-Type: application/json" -d '{"query": "How does Utkrusht pre-populate skill assessments?", "top_k": 3}'`
- Debug via ChromaDB API: `curl http://<DROPLET_IP>:8001/api/v1/collections`

---

## Quick Commands

```bash
# Start the stack
./run.sh

# Or manually
docker-compose up -d --build

# Check logs
docker logs rag-app
docker logs chroma-init

# Stop and clean up
./kill.sh

# Or manually
docker-compose down --volumes --remove-orphans

# Test health
curl http://localhost:8000/health

# Test query
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query": "What is a proof-of-skills marketplace?", "top_k": 3}'

# Check ChromaDB
curl http://localhost:8001/api/v1/heartbeat
curl http://localhost:8001/api/v1/collections
```

---

## Dependencies

```
chromadb>=0.5.23,<1.0.0
fastapi>=0.104.0,<1.0.0
uvicorn>=0.24.0,<1.0.0
pydantic>=2.0.0,<3.0.0
requests>=2.31.0,<3.0.0
python-dotenv>=1.0.0,<2.0.0
```

**Needs adding:** `sentence-transformers` (for explicit embedding model support)

---

## Sample Data Summary

25 documentation chunks covering: company overview, proof-of-skills concept, assessment design, RAG basics, ChromaDB usage, Docker architecture, embedding drift postmortem, best practices, pipeline flow, evaluation metrics, and more.