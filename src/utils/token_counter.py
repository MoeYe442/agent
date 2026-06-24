from __future__ import annotations


def count_tokens(text: str) -> int:
    """Count tokens in text. Uses tiktoken if available, falls back to char/4 estimation."""
    try:
        import tiktoken
        enc = tiktoken.get_encoding("cl100k_base")
        return len(enc.encode(text))
    except ImportError:
        return max(1, len(text) // 4)


def count_tokens_batch(texts: list[str]) -> list[int]:
    """Count tokens for a batch of texts."""
    return [count_tokens(t) for t in texts]
