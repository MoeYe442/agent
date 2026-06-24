from __future__ import annotations

import hashlib
import re
import uuid
from pathlib import Path

from src.models.enums import SourceType
from src.models.rag import RagChunk


def _content_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]


def chunk_text(
    text: str,
    chunk_size: int = 1500,
    chunk_overlap: int = 200,
    source_type: SourceType = SourceType.DOCUMENT,
    source_path: str = "",
) -> list[RagChunk]:
    """Split a text string into overlapping chunks using recursive character splitting.

    Tries to split on paragraph boundaries first, then sentences, then words.
    """
    if not text.strip():
        return []

    chunks: list[RagChunk] = []
    splits = _recursive_split(text, chunk_size, chunk_overlap)

    for i, segment in enumerate(splits):
        chunks.append(RagChunk(
            chunk_id=uuid.uuid4().hex,
            content=segment,
            source_type=source_type,
            source_path=source_path,
            chunk_index=i,
            metadata={
                "char_count": len(segment),
                "hash": _content_hash(segment),
            },
            token_count=len(segment) // 4,
        ))

    return chunks


def chunk_file(
    file_path: str | Path,
    chunk_size: int = 1500,
    chunk_overlap: int = 200,
) -> list[RagChunk]:
    """Read a file and split it into chunks."""
    p = Path(file_path)
    if not p.exists():
        return []
    try:
        content = p.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []

    ext = p.suffix.lower()
    source_type_map = {
        ".py": SourceType.CODE_FILE,
        ".js": SourceType.CODE_FILE,
        ".ts": SourceType.CODE_FILE,
        ".go": SourceType.CODE_FILE,
        ".rs": SourceType.CODE_FILE,
        ".java": SourceType.CODE_FILE,
        ".cpp": SourceType.CODE_FILE,
        ".c": SourceType.CODE_FILE,
        ".h": SourceType.CODE_FILE,
        ".md": SourceType.DOCUMENT,
        ".rst": SourceType.DOCUMENT,
        ".txt": SourceType.DOCUMENT,
    }
    source_type = source_type_map.get(ext, SourceType.DOCUMENT)

    return chunk_text(
        content,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        source_type=source_type,
        source_path=str(p),
    )


def chunk_documents(
    documents: list[tuple[str, str, str]],  # (content, source_path, source_type)
    chunk_size: int = 1500,
    chunk_overlap: int = 200,
) -> list[RagChunk]:
    """Chunk a list of documents into RagChunks.

    Each document is a tuple of (content, source_path, source_type_str).
    """
    all_chunks: list[RagChunk] = []
    for content, source_path, source_type_str in documents:
        try:
            st = SourceType(source_type_str)
        except ValueError:
            st = SourceType.DOCUMENT
        chunks = chunk_text(
            content,
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            source_type=st,
            source_path=source_path,
        )
        all_chunks.extend(chunks)
    return all_chunks


def _recursive_split(text: str, chunk_size: int, overlap: int) -> list[str]:
    """Recursively split text trying paragraph, sentence, and word boundaries."""
    if len(text) <= chunk_size:
        return [text] if text.strip() else []

    # Try splitting on double newlines (paragraphs)
    paragraphs = re.split(r"\n\s*\n", text)
    if len(paragraphs) > 1:
        return _merge_splits(paragraphs, chunk_size, overlap, "\n\n")

    # Try splitting on single newlines
    lines = text.split("\n")
    if len(lines) > 1:
        return _merge_splits(lines, chunk_size, overlap, "\n")

    # Try sentence splitting
    sentences = re.split(r"(?<=[.!?])\s+", text)
    if len(sentences) > 1:
        return _merge_splits(sentences, chunk_size, overlap, " ")

    # Fallback: character-level splitting
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        start = end - overlap
    return chunks


def _merge_splits(
    splits: list[str],
    chunk_size: int,
    overlap: int,
    separator: str,
) -> list[str]:
    """Merge small splits into chunks of approximately chunk_size."""
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for split in splits:
        split_len = len(split)
        if current_len + split_len > chunk_size and current:
            chunks.append(separator.join(current))
            # Keep overlap: retain last few items
            overlap_len = 0
            overlap_items: list[str] = []
            for item in reversed(current):
                if overlap_len + len(item) > overlap:
                    overlap_items.insert(0, item)
                    break
                overlap_items.insert(0, item)
                overlap_len += len(item) + len(separator)
            current = overlap_items
            current_len = overlap_len
        current.append(split)
        current_len += split_len + (len(separator) if current_len > 0 else 0)

    if current:
        chunks.append(separator.join(current))

    return chunks
