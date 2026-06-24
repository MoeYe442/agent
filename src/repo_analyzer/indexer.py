from __future__ import annotations

import asyncio
import hashlib
import uuid
from pathlib import Path

import structlog

from src.models.code_index import ProjectIndex
from src.models.rag import RagChunk
from src.repo_analyzer.parser import analyze_project_structure, extract_readme
from src.repo_analyzer.jedi_analyzer import build_project_index

logger = structlog.get_logger(__name__)


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def index_repo_files(root: Path, target_files: list[str] | None = None) -> list[RagChunk]:
    """Read project files and convert them to RagChunks for vector indexing.

    Each file becomes one or more chunks (large files are not split here —
    chunking is handled by the RAG pipeline).
    """
    root = Path(root)
    chunks: list[RagChunk] = []

    files_to_read: list[Path] = []
    if target_files:
        for tf in target_files:
            fp = root / tf
            if fp.exists() and fp.is_file():
                files_to_read.append(fp)
    else:
        structure = analyze_project_structure(root)
        for entry in structure["tree"]:
            if entry.endswith("/"):
                continue
            fp = root / entry
            if fp.exists() and fp.is_file():
                files_to_read.append(fp)

    for i, fpath in enumerate(files_to_read):
        try:
            content = fpath.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        if not content.strip():
            continue

        rel = str(fpath.relative_to(root))
        chunks.append(RagChunk(
            chunk_id=uuid.uuid4().hex,
            content=content,
            source_type="code_file",
            source_path=rel,
            chunk_index=i,
            metadata={
                "extension": fpath.suffix,
                "size_bytes": fpath.stat().st_size,
                "hash": _content_hash(content),
            },
            token_count=len(content) // 4,
        ))

    logger.info("repo_files_indexed", chunks=len(chunks))
    return chunks


async def index_project(
    root: Path,
    milvus_client,
    llm_client,
    collection_name: str = "code_research",
    target_files: list[str] | None = None,
) -> ProjectIndex:
    """Full project indexing pipeline:
    1. Build ProjectIndex via Jedi
    2. Read files into RagChunks
    3. Embed and insert into Milvus

    Returns the ProjectIndex.
    """
    project_index = build_project_index(root, target_files)
    chunks = index_repo_files(root, target_files)

    if not chunks:
        logger.warning("no_chunks_to_index")
        return project_index

    # Embed chunks
    texts = [c.content[:8000] for c in chunks]
    try:
        vectors = await asyncio.to_thread(llm_client.embed, texts)
    except Exception as exc:
        logger.error("embedding_failed", error=str(exc))
        return project_index

    # Insert into Milvus
    vectors_list = [list(v) for v in vectors]
    milvus_meta = []
    for c in chunks:
        milvus_meta.append({
            "id": c.chunk_id,
            "text": c.content[:8000],
            "source_path": c.source_path,
            "metadata": c.metadata,
        })

    try:
        await asyncio.to_thread(
            milvus_client.init_collection, collection_name, len(vectors_list[0]) if vectors_list else 384
        )
        await asyncio.to_thread(
            milvus_client.insert, collection_name, vectors_list, milvus_meta
        )
    except Exception as exc:
        logger.error("milvus_insert_failed", error=str(exc))

    return project_index
