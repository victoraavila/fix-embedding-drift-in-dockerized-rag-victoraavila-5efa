import asyncio
import logging
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse

from .models import QueryRequest, QueryResponse, ContextItem
from .rag_pipeline import retrieve_context, generate_answer
from .vector_store import ensure_collection_has_data

logger = logging.getLogger("uvicorn.error")

app = FastAPI(
    title="Utkrusht Documentation RAG API",
    description="RAG API for querying Utkrusht internal documentation using ChromaDB.",
    version="1.0.0",
)


@app.on_event("startup")
async def startup_event() -> None:
  """Wait briefly for ChromaDB and data to be available before serving traffic.

  The API will still start even if data is not yet available, but the health
  endpoint will reflect a degraded status.
  """
  max_attempts = 5
  delay_seconds = 2
  for attempt in range(1, max_attempts + 1):
      try:
          if ensure_collection_has_data():
              logger.info("ChromaDB collection is available and has data.")
              return
          else:
              logger.warning(
                  "ChromaDB reachable but collection appears empty (attempt %d/%d).",
                  attempt,
                  max_attempts,
              )
      except Exception as exc:  # noqa: BLE001
          logger.warning(
              "Waiting for ChromaDB to be ready (attempt %d/%d): %s",
              attempt,
              max_attempts,
              exc,
          )
      await asyncio.sleep(delay_seconds)

  logger.error(
      "ChromaDB not ready or collection has no data after %d attempts. "
      "API will still start, but queries may fail until data is available.",
      max_attempts,
  )


@app.get("/health")
async def health() -> JSONResponse:
    """Basic health check for the RAG API and ChromaDB connectivity."""
    try:
        ready = ensure_collection_has_data()
        status = "ok" if ready else "degraded"
        return JSONResponse({"status": status})
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=503, detail=f"ChromaDB not ready: {exc}") from exc


@app.post("/query", response_model=QueryResponse)
async def query_endpoint(request: QueryRequest) -> QueryResponse:
    """Query the RAG system for documentation-based answers."""
    try:
        contexts_raw = retrieve_context(request.query, request.top_k or 3)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"Error querying vector store: {exc}") from exc

    answer = generate_answer(request.query, contexts_raw)
    contexts = [ContextItem(**c) for c in contexts_raw]
    return QueryResponse(query=request.query, answer=answer, contexts=contexts)
