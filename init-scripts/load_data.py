import json
import os
import time
from pathlib import Path

import chromadb
import requests
from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction


EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-mpnet-base-v2")
embedding_function = SentenceTransformerEmbeddingFunction(model_name=EMBEDDING_MODEL)

CHROMA_HOST = os.getenv("CHROMA_HOST", "chromadb")
CHROMA_PORT = int(os.getenv("CHROMA_PORT", "8000"))
COLLECTION_NAME = os.getenv("CHROMA_COLLECTION", "utkrusht_docs")

MAX_RETRIES = 5
SLEEP_SECONDS = 5


def wait_for_chromadb() -> None:
    base_url = f"http://{CHROMA_HOST}:{CHROMA_PORT}"
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(f"{base_url}/api/v1/heartbeat", timeout=3)
            if resp.status_code == 200:
                print(f"[chroma-init] ChromaDB is ready on attempt {attempt}.")
                return
            else:
                print(
                    f"[chroma-init] Heartbeat returned status {resp.status_code} "
                    f"(attempt {attempt}/{MAX_RETRIES}).",
                )
        except Exception as exc:  # noqa: BLE001
            print(
                f"[chroma-init] Error reaching ChromaDB (attempt {attempt}/"
                f"{MAX_RETRIES}): {exc}",
            )
        time.sleep(SLEEP_SECONDS)

    raise RuntimeError(
        f"ChromaDB at {base_url} not ready after {MAX_RETRIES} attempts."
    )


def re_embed_collection(client: chromadb.HttpClient) -> None:
    existing = client.get_collection(name=COLLECTION_NAME)
    data = existing.get(include=["documents", "metadatas"])
    ids = data["ids"]
    documents = data["documents"]
    metadatas = data["metadatas"]

    if not ids:
        print(f"[chroma-init] Collection '{COLLECTION_NAME}' is empty — nothing to re-embed.")
        return

    print(f"[chroma-init] Re-embedding {len(ids)} documents from model to '{EMBEDDING_MODEL}'...")
    client.delete_collection(name=COLLECTION_NAME)
    new_collection = client.create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_function,
        metadata={"embedding_model": EMBEDDING_MODEL},
    )
    new_collection.add(ids=ids, documents=documents, metadatas=metadatas)
    print(f"[chroma-init] Re-embedded {len(ids)} documents with '{EMBEDDING_MODEL}'.")

    test_results = new_collection.query(query_texts=["proof-of-skills marketplace"], n_results=2)
    print(f"[chroma-init] Post re-embed verification query returned: {test_results.get('ids')}")


def load_sample_data() -> None:
    client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)

    collections = client.list_collections()
    collection_exists = COLLECTION_NAME in collections

    if collection_exists:
        existing = client.get_collection(name=COLLECTION_NAME)
        stored_model = existing.metadata.get("embedding_model") if existing.metadata else None

        if stored_model and stored_model != EMBEDDING_MODEL:
            print(
                f"[chroma-init] Embedding drift detected: stored model='{stored_model}', "
                f"configured model='{EMBEDDING_MODEL}'. Re-embedding..."
            )
            re_embed_collection(client)
            return

        count = existing.count()
        if count > 0:
            if not stored_model:
                print(
                    f"[chroma-init] Collection '{COLLECTION_NAME}' has {count} documents "
                    f"but no embedding_model metadata. Re-embedding to tag with '{EMBEDDING_MODEL}'..."
                )
                re_embed_collection(client)
                return

            print(
                f"[chroma-init] Collection '{COLLECTION_NAME}' already has data "
                f"(count={count}, model='{stored_model}'). No drift detected — skipping."
            )
            return

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        embedding_function=embedding_function,
        metadata={"embedding_model": EMBEDDING_MODEL},
    )

    data_path = Path("/app/init-scripts/sample_data.json")
    with data_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    ids = [str(item["id"]) for item in raw]
    documents = [item["text"] for item in raw]
    metadatas = [item.get("metadata", {}) for item in raw]

    print(f"[chroma-init] Adding {len(ids)} documents to collection '{COLLECTION_NAME}' with model '{EMBEDDING_MODEL}'.")
    collection.add(ids=ids, documents=documents, metadatas=metadatas)

    test_query = "proof-of-skills marketplace"
    results = collection.query(query_texts=[test_query], n_results=2)
    print(f"[chroma-init] Test query results: {results.get('ids')}")


if __name__ == "__main__":
    print(f"[chroma-init] Configured embedding model: {EMBEDDING_MODEL}")
    print("[chroma-init] Waiting for ChromaDB to be ready...")
    wait_for_chromadb()
    print("[chroma-init] Loading / verifying data in ChromaDB...")
    load_sample_data()
    print("[chroma-init] Initialization completed successfully.")