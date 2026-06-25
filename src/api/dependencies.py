from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from src.config import Settings

_settings: Settings | None = None
_redis: Any = None
_llm: Any = None
_rag: Any = None
_UNSET = object()
_executor: Any = None


def get_settings() -> Settings:
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


async def get_redis():
    global _redis
    if _redis is None:
        from src.infrastructure.redis import get_redis_client
        from src.infrastructure.memory_store import InMemoryStore
        settings = get_settings()
        try:
            _redis = get_redis_client()
            await _redis.connect()
        except Exception:
            import structlog
            structlog.get_logger(__name__).warning("redis_unavailable_falling_back_to_memory")
            _redis = InMemoryStore()
            await _redis.connect()
    return _redis


def get_llm():
    global _llm
    if _llm is None:
        from src.infrastructure.llm import get_llm_client
        _llm = get_llm_client()
    return _llm


async def get_rag() -> Any:
    global _rag
    if _rag is None:
        settings = get_settings()
        llm = get_llm()
        milvus = None
        try:
            from src.infrastructure.milvus import get_milvus_client
            milvus = get_milvus_client()
            await milvus._ensure_connection()
        except Exception:
            import structlog
            structlog.get_logger(__name__).warning("milvus_unavailable_using_bm25_only")

        try:
            from src.rag.pipeline import RAGPipeline
            _rag = RAGPipeline(
                milvus_client=milvus,
                llm_client=llm,
                collection_name=settings.milvus_collection_name,
                embedding_dim=settings.embedding_dim,
            )
        except Exception:
            import structlog
            structlog.get_logger(__name__).warning("rag_unavailable", exc_info=True)
            _rag = False  # sentinel: tried and failed
    return _rag if _rag is not False else None


async def get_workflow_executor():
    global _executor
    if _executor is None:
        from src.workflow.executor import WorkflowExecutor
        llm = get_llm()
        redis = await get_redis()
        rag = await get_rag()
        _executor = WorkflowExecutor(
            llm_client=llm,
            redis_client=redis,
            rag_pipeline=rag,
        )
    return _executor


async def cleanup() -> None:
    """Clean up resources on shutdown."""
    global _redis, _llm, _executor
    if _redis is not None:
        try:
            await _redis.disconnect()
        except Exception:
            pass
        _redis = None
    if _llm is not None:
        try:
            _llm.close()
        except Exception:
            pass
        _llm = None
    _executor = None
    _rag = None
