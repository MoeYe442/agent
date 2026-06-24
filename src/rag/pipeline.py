from __future__ import annotations

import asyncio
from typing import Any

import structlog

from src.models.rag import RagChunk, RetrievalResult, SearchQuery
from src.rag.bm25_index import BM25Index
from src.rag.chunker import chunk_documents, chunk_file, chunk_text
from src.rag.hybrid_search import hybrid_search, rerank_results
from src.rag.indexer import index_chunks

logger = structlog.get_logger(__name__)


class RAGPipeline:
    """High-level RAG pipeline combining chunking, indexing, and hybrid search."""

    def __init__(
        self,
        milvus_client: Any,
        llm_client: Any,
        collection_name: str = "code_research",
        embedding_dim: int = 384,
    ) -> None:
        self._milvus = milvus_client
        self._llm = llm_client
        self._collection = collection_name
        self._embedding_dim = embedding_dim
        self._bm25 = BM25Index()
        self._chunked: list[RagChunk] = []

    async def ingest_texts(
        self,
        texts: list[str],
        source_paths: list[str] | None = None,
        source_types: list[str] | None = None,
    ) -> int:
        """Ingest and index a list of text documents."""
        if source_paths is None:
            source_paths = [""] * len(texts)
        if source_types is None:
            source_types = ["document"] * len(texts)

        documents = list(zip(texts, source_paths, source_types))
        chunks = chunk_documents(documents)
        return await self._ingest_chunks(chunks)

    async def ingest_files(self, file_paths: list[str]) -> int:
        """Ingest and index a list of files."""
        chunks: list[RagChunk] = []
        for fp in file_paths:
            chunks.extend(chunk_file(fp))
        return await self._ingest_chunks(chunks)

    async def search(
        self,
        query: str,
        top_k: int = 10,
        alpha: float = 0.5,
        filters: dict | None = None,
        rerank: bool = True,
    ) -> list[RetrievalResult]:
        """Search the RAG pipeline with hybrid retrieval and optional reranking."""
        sq = SearchQuery(
            query_text=query,
            top_k=top_k,
            alpha=alpha,
            filters=filters,
        )
        results = await hybrid_search(
            sq,
            self._bm25,
            self._milvus,
            self._llm,
            self._collection,
            top_k=top_k,
        )
        if rerank and results:
            results = await rerank_results(results, query, self._llm, top_k)
        return results

    async def _ingest_chunks(self, chunks: list[RagChunk]) -> int:
        """Index chunks into Milvus and BM25."""
        if not chunks:
            return 0

        n = await index_chunks(chunks, self._milvus, self._llm, self._collection, self._embedding_dim)
        if n > 0:
            self._chunked.extend(chunks)
            self._bm25.build(self._chunked)
        return n

    @property
    def chunk_count(self) -> int:
        return len(self._chunked)
