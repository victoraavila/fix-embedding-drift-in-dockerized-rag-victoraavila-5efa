import os

CHROMA_HOST: str = os.getenv("CHROMA_HOST", "chromadb")
CHROMA_PORT: int = int(os.getenv("CHROMA_PORT", "8000"))
COLLECTION_NAME: str = os.getenv("CHROMA_COLLECTION", "utkrusht_docs")
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-mpnet-base-v2")

# Retry settings for ChromaDB connectivity
CHROMA_RETRY_ATTEMPTS: int = int(os.getenv("CHROMA_RETRY_ATTEMPTS", "5"))
CHROMA_RETRY_SLEEP_SECONDS: int = int(os.getenv("CHROMA_RETRY_SLEEP_SECONDS", "2"))
