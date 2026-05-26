#!/usr/bin/env python3
"""Re-embed all documents if the configured embedding model differs from the stored one.

Can be run manually inside the rag-app container or as a one-shot docker-compose run.

Usage:
    docker exec rag-app python /app/scripts/re_embed.py
    docker-compose run --rm rag-app python /app/scripts/re_embed.py
"""

import os
import sys
import time

import chromadb
import requests
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction

CHROMA_HOST = os.getenv("CHROMA_HOST", "chromadb")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
COLLECTION_NAME = os.getenv("CHROMA_COLLECTION", "utkrusht_docs")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-mpnet-base-v2")

MAX_RETRIES = 10
RETRY_DELAY = 3

EMBEDDING_METADATA_KEY = "embedding_model"


def wait_for_chromadb():
    base_url = f"http://{CHROMA_HOST}:{CHROMA_PORT}"
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(f"{base_url}/api/v1/heartbeat", timeout=3)
            if resp.status_code == 200:
                print(f"[re-embed] ChromaDB is ready (attempt {attempt}).")
                return
        except Exception:
            pass
        print(f"[re-embed] Waiting for ChromaDB (attempt {attempt}/{MAX_RETRIES})...")
        time.sleep(RETRY_DELAY)
    raise RuntimeError(f"ChromaDB at {base_url} not ready after {MAX_RETRIES} attempts.")


def main():
    print(f"[re-embed] Configured embedding model: {EMBEDDING_MODEL}")
    embedding_function = SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)
    wait_for_chromadb()

    client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)

    collections = client.list_collections()
    if not any(c.name == COLLECTION_NAME for c in collections):
        print(f"[re-embed] Collection '{COLLECTION_NAME}' does not exist. Nothing to re-embed.")
        return

    existing = client.get_collection(name=COLLECTION_NAME)
    stored_model = existing.metadata.get(EMBEDDING_METADATA_KEY) if existing.metadata else None

    if stored_model == EMBEDDING_MODEL:
        print(f"[re-embed] No drift detected — stored model '{stored_model}' matches configured model. Nothing to do.")
        return

    if stored_model:
        print(f"[re-embed] Drift detected: stored='{stored_model}', configured='{EMBEDDING_MODEL}'.")
    else:
        print(f"[re-embed] No embedding model metadata found. Re-embedding with '{EMBEDDING_MODEL}'.")

    data = existing.get(include=["documents", "metadatas"])
    ids = data["ids"]
    documents = data["documents"]
    metadatas = data["metadatas"]

    if not ids:
        print("[re-embed] Collection is empty — nothing to re-embed.")
        return

    print(f"[re-embed] Re-embedding {len(ids)} documents with '{EMBEDDING_MODEL}'...")
    client.delete_collection(name=COLLECTION_NAME)
    new_collection = client.create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_function,
        metadata={EMBEDDING_METADATA_KEY: EMBEDDING_MODEL},
    )
    new_collection.add(ids=ids, documents=documents, metadatas=metadatas)

    test_results = new_collection.query(query_texts=["proof-of-skills marketplace"], n_results=2)
    print(f"[re-embed] Verification query returned: {test_results.get('ids')}")
    print(f"[re-embed] Done. {len(ids)} documents re-embedded with '{EMBEDDING_MODEL}'.")


if __name__ == "__main__":
    main()