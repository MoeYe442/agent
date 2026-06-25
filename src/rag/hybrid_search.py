from __future__ import annotations

import asyncio
import math
from collections import defaultdict
from typing import Any

import structlog

from src.models.rag import RagChunk, RetrievalResult, SearchQuery

logger = structlog.get_logger(__name__)


async def hybrid_search(
    query: SearchQuery,
    bm25_index: Any,  # BM25Index
    milvus_client: Any,
    llm_client: Any,
    collection_name: str = "code_research",
    top_k: int = 10,
) -> list[RetrievalResult]:
    """Perform hybrid search combining BM25 and vector similarity.

    Uses weighted rank fusion (WRF) to combine scores:
        combined_score = alpha * bm25_score + (1-alpha) * vector_score

    Args:
        query: The SearchQuery with alpha controlling BM25 vs vector weight
        bm25_index: BM25Index instance
        milvus_client: MilvusClientWrapper instance
        llm_client: LLMClient instance (for embeddings)
        collection_name: Milvus collection name
        top_k: Number of results to return

    Returns ranked list of RetrievalResult objects.
    """
    alpha = max(0.0, min(1.0, query.alpha))
    fetch_k = max(top_k * 3, 30)

    # BM25 search
    bm25_results: dict[str, tuple[RagChunk, float]] = {}
    if bm25_index is not None and bm25_index.chunk_count > 0:
        for chunk, score in bm25_index.search(query.query_text, top_k=fetch_k):
            bm25_results[chunk.chunk_id] = (chunk, score)

    # Vector search (skip when Milvus is unavailable)
    vector_results: dict[str, float] = {}
    if milvus_client is not None:
        try:
            query_vector = await asyncio.to_thread(llm_client.embed, [query.query_text])
            if query_vector:
                hits = await asyncio.to_thread(
                    milvus_client.search,
                    collection_name,
                    list(query_vector[0]),
                    fetch_k,
                    query.filters,
                )
                for hit in hits:
                    chunk_id = hit.get("id", "")
                    score = hit.get("score", hit.get("distance", 0.0))
                    # Normalize cosine distance to similarity
                    if "distance" in hit:
                        score = 1.0 - score
                    vector_results[chunk_id] = float(score)
        except Exception as exc:
            logger.warning("vector_search_failed", error=str(exc))

    # Weighted fusion
    fused: dict[str, tuple[RagChunk, float, float | None, float | None]] = {}
    all_ids = set(bm25_results.keys()) | set(vector_results.keys())

    for chunk_id in all_ids:
        bm25_score = bm25_results[chunk_id][1] if chunk_id in bm25_results else 0.0
        vec_score = vector_results.get(chunk_id, 0.0)

        # Normalize scores to [0, 1] range for fusion
        bm25_norm = _normalize_score(bm25_score, bm25_results.values() if bm25_results else [])
        vec_norm = _normalize_score(vec_score, vector_results.values() if vector_results else [])

        combined = alpha * bm25_norm + (1 - alpha) * vec_norm

        chunk = bm25_results.get(chunk_id, (None, 0))[0]
        if chunk is None:
            # Create a minimal chunk from vector result metadata
            chunk = RagChunk(
                chunk_id=chunk_id,
                content="",
                source_type="code_file",
                source_path="",
                chunk_index=0,
            )

        fused[chunk_id] = (chunk, combined, bm25_score if chunk_id in bm25_results else None, vec_score if chunk_id in vector_results else None)

    # Sort by combined score and return top_k
    sorted_ids = sorted(fused.items(), key=lambda x: x[1][1], reverse=True)[:top_k]

    results: list[RetrievalResult] = []
    for rank, (chunk_id, (chunk, combined_score, bm25, vs)) in enumerate(sorted_ids, 1):
        results.append(RetrievalResult(
            chunk=chunk,
            score=round(combined_score, 4),
            bm25_score=round(bm25, 4) if bm25 is not None else None,
            vector_score=round(vs, 4) if vs is not None else None,
            rank=rank,
        ))

    logger.info("hybrid_search_completed", query=query.query_text[:80], results=len(results))
    return results


async def rerank_results(
    results: list[RetrievalResult],
    query_text: str,
    llm_client: Any,
    top_k: int = 10,
) -> list[RetrievalResult]:
    """Re-rank retrieval results using an LLM-based cross-encoder approach.

    Uses the LLM to score each chunk's relevance to the query.
    Falls back to original ranking if LLM is unavailable.
    """
    if not results:
        return results

    # Use LLM as a cross-encoder via a scoring prompt
    scored: list[tuple[RetrievalResult, float]] = []
    for r in results:
        content_preview = r.chunk.content[:2000]
        source = r.chunk.source_path

        prompt = f"""Rate the relevance of this document to the query on a scale of 0 to 1.
Query: {query_text}
Document source: {source}
Document content:
{content_preview}

Relevance score (0-1, where 1 is perfectly relevant and 0 is irrelevant):"""

        try:
            messages = [{"role": "user", "content": prompt}]
            resp = await asyncio.to_thread(
                llm_client.chat, messages, None, 0.0
            )
            content = resp.get("choices", [{}])[0].get("message", {}).get("content", "")
            # Parse the score
            try:
                rerank_score = float(content.strip())
                rerank_score = max(0.0, min(1.0, rerank_score))
            except ValueError:
                rerank_score = r.score
        except Exception:
            rerank_score = r.score

        combined = 0.7 * rerank_score + 0.3 * r.score
        scored.append((r, combined))

    scored.sort(key=lambda x: x[1], reverse=True)
    reranked = scored[:top_k]

    # Update results with new scores and ranks
    final: list[RetrievalResult] = []
    for rank, (result, new_score) in enumerate(reranked, 1):
        final.append(RetrievalResult(
            chunk=result.chunk,
            score=round(new_score, 4),
            bm25_score=result.bm25_score,
            vector_score=result.vector_score,
            rank=rank,
        ))

    return final


def _normalize_score(score: float, scores: Any) -> float:
    """Min-max normalize a score based on a collection of (chunk, score) tuples or float values."""
    if not scores:
        return score

    if isinstance(scores, dict):
        scores = [v for _, v in scores.items()]

    values = []
    for s in scores:
        if isinstance(s, (int, float)):
            values.append(s)
        elif isinstance(s, tuple) and len(s) >= 2:
            values.append(s[1])

    if not values or max(values) == min(values):
        return score

    mn = min(values)
    mx = max(values)
    if mx == mn:
        return 0.5
    return (score - mn) / (mx - mn)
