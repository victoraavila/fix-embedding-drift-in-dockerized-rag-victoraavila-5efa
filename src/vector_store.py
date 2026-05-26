import os
import time
from typing import Any, Dict

import chromadb
import requests

from .config import (
    CHROMA_HOST,
    CHROMA_PORT,
    COLLECTION_NAME,
    CHROMA_RETRY_ATTEMPTS,
    CHROMA_RETRY_SLEEP_SECONDS,
)


def _wait_for_chromadb() -> None:
    """Wait for ChromaDB's HTTP API to become available with simple retries."""
    base_url = f"http://{CHROMA_HOST}:{CHROMA_PORT}"
    for attempt in range(1, CHROMA_RETRY_ATTEMPTS + 1):
        try:
            resp = requests.get(f"{base_url}/api/v1/heartbeat", timeout=3)
            if resp.status_code == 200:
                return
        except Exception:
            # Ignore and retry
            pass
        time.sleep(CHROMA_RETRY_SLEEP_SECONDS)

    raise RuntimeError(
        f"ChromaDB at {base_url} not reachable after "
        f"{CHROMA_RETRY_ATTEMPTS} attempts."
    )


def get_client() -> chromadb.HttpClient:
    """Return a ChromaDB HTTP client, waiting for readiness if needed."""
    _wait_for_chromadb()
    client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
    return client


def get_collection() -> Any:
    """Get or create the main collection used by the RAG app."""
    client = get_client()
    return client.get_or_create_collection(name=COLLECTION_NAME)


def ensure_collection_has_data(min_docs: int = 1) -> bool:
    """Return True if the collection exists and has at least `min_docs` entries."""
    coll = get_collection()
    try:
        count = coll.count()
    except Exception:
        # Fallback in case `count` is unavailable
        results: Dict[str, Any] = coll.get(limit=min_docs)
        count = len(results.get("ids", []))
    return count >= min_docs


def query_collection(query_text: str, top_k: int = 3) -> Dict[str, Any]:
    """Run a similarity search against the collection using the default embeddings."""
    coll = get_collection()
    results = coll.query(query_texts=[query_text], n_results=top_k)
    return results
