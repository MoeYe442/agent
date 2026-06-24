from __future__ import annotations

import pytest

from src.models.enums import SourceType


class TestChunker:
    def test_chunk_text_basic(self):
        from src.rag.chunker import chunk_text

        text = "Hello world. " * 500
        chunks = chunk_text(text, chunk_size=200, chunk_overlap=50)
        assert len(chunks) > 0
        for c in chunks:
            assert c.content
            assert c.source_type in SourceType
            assert c.chunk_id

    def test_chunk_text_empty(self):
        from src.rag.chunker import chunk_text

        chunks = chunk_text("")
        assert chunks == []

    def test_chunk_text_short(self):
        from src.rag.chunker import chunk_text

        chunks = chunk_text("Short text", chunk_size=1000)
        assert len(chunks) == 1
        assert chunks[0].content == "Short text"

    def test_chunk_documents(self):
        from src.rag.chunker import chunk_documents

        docs = [
            ("Document one content here.", "/path/doc1.txt", "document"),
            ("print('hello world')", "/path/code.py", "code_file"),
        ]
        chunks = chunk_documents(docs, chunk_size=100)
        assert len(chunks) >= 2


class TestBM25Index:
    def test_build_and_search(self):
        from src.rag.bm25_index import BM25Index
        from src.models.rag import RagChunk
        from src.models.enums import SourceType

        # Build with explicit chunks containing keyword repetition
        chunks = [
            RagChunk(chunk_id=f"c{i}", content=content, source_type=SourceType.CODE_FILE, source_path=f"f{i}.py", chunk_index=i)
            for i, content in enumerate([
                "async programming with asyncio and coroutines in Python",
                "using asyncio for concurrent programming tasks",
                "async await syntax for non-blocking code",
                "FastAPI web framework for building APIs",
                "Python async programming best practices and patterns",
            ])
        ]
        bm25 = BM25Index()
        bm25.build(chunks)
        assert bm25.chunk_count == 5

        results = bm25.search("async programming", top_k=5)
        assert len(results) > 0, f"Expected results for 'async programming' search"
        chunk, score = results[0]
        assert score > 0

    def test_empty_search(self):
        from src.rag.bm25_index import BM25Index

        bm25 = BM25Index()
        results = bm25.search("test")
        assert results == []

    def test_serialization(self, tmp_path):
        from src.rag.bm25_index import BM25Index
        from src.rag.chunker import chunk_text

        chunks = chunk_text("Test content for serialization.", chunk_size=100)
        bm25 = BM25Index()
        bm25.build(chunks)

        path = tmp_path / "bm25.pkl"
        bm25.save(path)

        bm25_loaded = BM25Index()
        bm25_loaded.load(path)
        assert bm25_loaded.chunk_count == len(chunks)
