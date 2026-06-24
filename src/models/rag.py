from __future__ import annotations

from pydantic import BaseModel, Field

from src.models.enums import SourceType


class RagChunk(BaseModel):
    chunk_id: str
    content: str
    source_type: SourceType
    source_path: str
    chunk_index: int
    metadata: dict = Field(default_factory=dict)
    token_count: int = 0


class SearchQuery(BaseModel):
    query_text: str
    top_k: int = 10
    alpha: float = 0.5  # BM25 weight (1-alpha = vector weight)
    filters: dict | None = None


class RetrievalResult(BaseModel):
    chunk: RagChunk
    score: float
    bm25_score: float | None = None
    vector_score: float | None = None
    rank: int
