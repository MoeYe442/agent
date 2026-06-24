from __future__ import annotations

import json
import pickle
from pathlib import Path

from src.models.rag import RagChunk


class BM25Index:
    """Local BM25 index for keyword-based retrieval.

    Wraps rank-bm25 with serialization support.
    """

    def __init__(self) -> None:
        self._chunks: list[RagChunk] = []
        self._bm25: object = None
        self._corpus: list[list[str]] = []

    def build(self, chunks: list[RagChunk]) -> None:
        """Build BM25 index from a list of RagChunks."""
        from rank_bm25 import BM25Okapi

        self._chunks = chunks
        self._corpus = [_tokenize(c.content) for c in chunks]
        try:
            self._bm25 = BM25Okapi(self._corpus)
        except ValueError:
            self._bm25 = None

    def search(self, query: str, top_k: int = 10) -> list[tuple[RagChunk, float]]:
        """Search the BM25 index. Returns list of (chunk, score) tuples."""
        if self._bm25 is None or not self._chunks:
            return []

        query_tokens = _tokenize(query)
        try:
            scores = self._bm25.get_scores(query_tokens)
        except Exception:
            return []

        # Get top-k indices sorted by score descending
        indexed_scores = list(enumerate(scores))
        indexed_scores.sort(key=lambda x: x[1], reverse=True)
        top = indexed_scores[:top_k]

        return [(self._chunks[i], float(score)) for i, score in top if score > 0]

    def save(self, path: str | Path) -> None:
        """Serialize BM25 index to disk."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        state = {
            "chunks": [c.model_dump() for c in self._chunks],
            "corpus": self._corpus,
        }
        with open(p, "wb") as f:
            pickle.dump(state, f)

    def load(self, path: str | Path) -> None:
        """Deserialize BM25 index from disk."""
        p = Path(path)
        if not p.exists():
            return
        with open(p, "rb") as f:
            state = pickle.load(f)

        from rank_bm25 import BM25Okapi

        self._chunks = [RagChunk(**c) for c in state["chunks"]]
        self._corpus = state["corpus"]
        try:
            self._bm25 = BM25Okapi(self._corpus)
        except ValueError:
            self._bm25 = None

    @property
    def chunk_count(self) -> int:
        return len(self._chunks)


def _tokenize(text: str) -> list[str]:
    """Simple whitespace + punctuation tokenizer for BM25."""
    import re
    tokens = re.findall(r"[a-zA-Z0-9_]+", text.lower())
    return tokens
