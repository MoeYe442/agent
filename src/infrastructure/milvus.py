from __future__ import annotations

from typing import Any

import structlog
from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    MilvusClient,
    connections,
    utility,
)

from src.config import Settings

logger = getattr(structlog, "get_logger")("src.infrastructure.milvus")

# Fixed field names used for every collection created by this wrapper.
_FIELD_ID = "id"
_FIELD_VECTOR = "vector"
_FIELD_TEXT = "text"
_FIELD_SOURCE_PATH = "source_path"
_FIELD_METADATA = "metadata"


class _MilvusClientWrapper:
    """Async-friendly wrapper around pymilvus (sync) for vector operations."""

    def __init__(self, host: str, port: int) -> None:
        self._host = host
        self._port = port
        self._alias = "default"
        self._connected = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _ensure_connection(self) -> None:
        if self._connected:
            return
        connections.connect(alias=self._alias, host=self._host, port=str(self._port))
        self._connected = True
        logger.info("milvus_connected", host=self._host, port=self._port)

    def disconnect(self) -> None:
        if self._connected:
            connections.disconnect(alias=self._alias)
            self._connected = False
            logger.info("milvus_disconnected")

    async def __aenter__(self) -> _MilvusClientWrapper:
        self._ensure_connection()
        return self

    async def __aexit__(self, *args: Any) -> None:
        self.disconnect()

    async def health_check(self) -> bool:
        """Check connectivity by listing collections."""
        try:
            self._ensure_connection()
            utility.list_collections(using=self._alias)
            return True
        except Exception:
            logger.exception("milvus_health_check_failed")
            return False

    # ------------------------------------------------------------------
    # Collection management
    # ------------------------------------------------------------------

    def init_collection(self, name: str, dim: int) -> None:
        """Create a collection with the standard schema if it does not exist."""
        self._ensure_connection()

        if utility.has_collection(name, using=self._alias):
            collection = Collection(name, using=self._alias)
            collection.load()
            logger.info("milvus_collection_loaded", name=name)
            return

        fields = [
            FieldSchema(name=_FIELD_ID, dtype=DataType.VARCHAR, is_primary=True, max_length=128),
            FieldSchema(name=_FIELD_VECTOR, dtype=DataType.FLOAT_VECTOR, dim=dim),
            FieldSchema(name=_FIELD_TEXT, dtype=DataType.VARCHAR, max_length=65535),
            FieldSchema(name=_FIELD_SOURCE_PATH, dtype=DataType.VARCHAR, max_length=1024),
            FieldSchema(name=_FIELD_METADATA, dtype=DataType.JSON),
        ]
        schema = CollectionSchema(fields, description=f"Collection: {name}")
        collection = Collection(name, schema=schema, using=self._alias)

        index_params = {
            "metric_type": "COSINE",
            "index_type": "IVF_FLAT",
            "params": {"nlist": 128},
        }
        collection.create_index(field_name=_FIELD_VECTOR, index_params=index_params)
        collection.load()
        logger.info("milvus_collection_created", name=name, dim=dim)

    def collection_exists(self, name: str) -> bool:
        self._ensure_connection()
        return utility.has_collection(name, using=self._alias)

    # ------------------------------------------------------------------
    # Data operations
    # ------------------------------------------------------------------

    def insert(
        self,
        collection: str,
        vectors: list[list[float]],
        metadata: list[dict[str, Any]],
    ) -> list[str]:
        """Insert vectors with metadata. Returns list of primary key IDs."""
        self._ensure_connection()
        col = Collection(collection, using=self._alias)

        rows = []
        for i, (vec, meta) in enumerate(zip(vectors, metadata)):
            row = {
                _FIELD_ID: meta.get(_FIELD_ID, f"{collection}_{i}"),
                _FIELD_VECTOR: vec,
                _FIELD_TEXT: meta.get(_FIELD_TEXT, meta.get("text", "")),
                _FIELD_SOURCE_PATH: meta.get(_FIELD_SOURCE_PATH, meta.get("source_path", "")),
                _FIELD_METADATA: meta.get(_FIELD_METADATA, meta),
            }
            rows.append(row)

        mr = col.insert(rows)
        logger.info("milvus_insert", collection=collection, count=len(rows))
        # mr.primary_keys is a DataType list; convert to Python strings
        return [str(pk) for pk in mr.primary_keys]

    def search(
        self,
        collection: str,
        query_vector: list[float],
        top_k: int,
        filters: dict | None = None,
    ) -> list[dict[str, Any]]:
        """Search for top_k nearest vectors. Returns list of hit dicts."""
        self._ensure_connection()
        col = Collection(collection, using=self._alias)

        search_params = {"metric_type": "COSINE", "params": {"nprobe": 16}}
        expr = _build_filter_expr(filters)

        results = col.search(
            data=[query_vector],
            anns_field=_FIELD_VECTOR,
            param=search_params,
            limit=top_k,
            expr=expr,
            output_fields=[_FIELD_ID, _FIELD_TEXT, _FIELD_SOURCE_PATH, _FIELD_METADATA],
        )

        hits: list[dict[str, Any]] = []
        for hit_group in results:
            for hit in hit_group:
                hits.append(
                    {
                        "id": hit.id,
                        "distance": hit.distance,
                        "score": hit.score,
                        "text": hit.entity.get(_FIELD_TEXT, ""),
                        "source_path": hit.entity.get(_FIELD_SOURCE_PATH, ""),
                        "metadata": hit.entity.get(_FIELD_METADATA, {}),
                    }
                )
        return hits

    def delete_by_ids(self, collection: str, ids: list[str]) -> None:
        """Delete entities by primary key IDs."""
        self._ensure_connection()
        col = Collection(collection, using=self._alias)
        expr = f'{_FIELD_ID} in [{", ".join(repr(rid) for rid in ids)}]'
        col.delete(expr)
        logger.info("milvus_deleted", collection=collection, count=len(ids))


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _build_filter_expr(filters: dict | None) -> str | None:
    """Build a Milvus scalar filter expression from a dict.

    Example: {"source_path": "src/main.py"} -> 'source_path == "src/main.py"'
    """
    if not filters:
        return None
    parts: list[str] = []
    for k, v in filters.items():
        if isinstance(v, str):
            parts.append(f'{k} == "{v}"')
        else:
            parts.append(f"{k} == {v}")
    return " and ".join(parts)


# ------------------------------------------------------------------
# Factory
# ------------------------------------------------------------------


def get_milvus_client() -> _MilvusClientWrapper:  # noqa: D103
    settings = Settings()
    return _MilvusClientWrapper(host=settings.milvus_host, port=settings.milvus_port)
