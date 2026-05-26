import json
import os
import time
from pathlib import Path

import chromadb
import requests


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


def load_sample_data() -> None:
    client = chromadb.HttpClient(host=CHROMA_HOST, port=CHROMA_PORT)
    collection = client.get_or_create_collection(name=COLLECTION_NAME)

    # Idempotency: if the collection already has data, do not duplicate.
    try:
        existing_count = collection.count()
    except Exception:
        existing_count = len(collection.get(limit=1).get("ids", []))

    if existing_count > 0:
        print(f"[chroma-init] Collection '{COLLECTION_NAME}' already has data (count ~ {existing_count}). Skipping load.")
        return

    data_path = Path("/app/init-scripts/sample_data.json")
    with data_path.open("r", encoding="utf-8") as f:
        raw = json.load(f)

    ids = [str(item["id"]) for item in raw]
    documents = [item["text"] for item in raw]
    metadatas = [item.get("metadata", {}) for item in raw]

    print(f"[chroma-init] Adding {len(ids)} documents to collection '{COLLECTION_NAME}'.")
    collection.add(ids=ids, documents=documents, metadatas=metadatas)

    # Simple verification query
    test_query = "proof-of-skills marketplace"
    results = collection.query(query_texts=[test_query], n_results=2)
    print(f"[chroma-init] Test query results: {results.get('ids')}")


if __name__ == "__main__":
    print("[chroma-init] Waiting for ChromaDB to be ready...")
    wait_for_chromadb()
    print("[chroma-init] Loading sample data into ChromaDB...")
    load_sample_data()
    print("[chroma-init] Initialization completed successfully.")
