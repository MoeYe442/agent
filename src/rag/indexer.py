from __future__ import annotations

import asyncio
from typing import Any

import structlog

from src.models.rag import RagChunk

logger = structlog.get_logger(__name__)


async def index_chunks(
    chunks: list[RagChunk],
    milvus_client: Any,
    llm_client: Any,
    collection_name: str = "code_research",
    embedding_dim: int = 384,
) -> int:
    """Embed a list of RagChunks and insert them into Milvus.

    Returns the number of chunks indexed.
    """
    if not chunks:
        return 0

    texts = [c.content[:8000] for c in chunks]
    try:
        vectors = await asyncio.to_thread(llm_client.embed, texts)
    except Exception as exc:
        logger.error("embedding_failed", error=str(exc))
        return 0

    vectors_list = [list(v) for v in vectors]
    metadata_list = [
        {
            "id": c.chunk_id,
            "text": c.content[:8000],
            "source_path": c.source_path,
            "metadata": {
                "source_type": str(c.source_type),
                "chunk_index": c.chunk_index,
                **c.metadata,
            },
        }
        for c in chunks
    ]

    try:
        await asyncio.to_thread(
            milvus_client.init_collection, collection_name, len(vectors_list[0])
        )
        await asyncio.to_thread(
            milvus_client.insert, collection_name, vectors_list, metadata_list
        )
    except Exception as exc:
        logger.error("milvus_insert_failed", error=str(exc))
        return 0

    logger.info("chunks_indexed", count=len(chunks), collection=collection_name)
    return len(chunks)


async def delete_index(
    milvus_client: Any,
    collection_name: str = "code_research",
    chunk_ids: list[str] | None = None,
) -> None:
    """Delete indexed chunks from Milvus. If chunk_ids is None, deletes all."""
    if chunk_ids:
        await asyncio.to_thread(milvus_client.delete_by_ids, collection_name, chunk_ids)
    else:
        logger.warning("bulk_delete_not_supported", collection=collection_name)
