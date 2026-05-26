from typing import Optional, List, Any, Dict

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    query: str = Field(..., description="User's natural language query.")
    top_k: Optional[int] = Field(
        3,
        ge=1,
        le=10,
        description="Number of documents to retrieve from ChromaDB.",
    )


class ContextItem(BaseModel):
    id: str
    text: str
    metadata: Dict[str, Any]


class QueryResponse(BaseModel):
    query: str
    answer: str
    contexts: List[ContextItem]
