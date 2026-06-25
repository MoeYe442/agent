from __future__ import annotations

from typing import Any, AsyncIterator

import httpx
import structlog
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from src.config import Settings

logger = getattr(structlog, "get_logger")("src.infrastructure.llm")


class LLMClient:
    """OpenAI-compatible LLM client using httpx."""

    def __init__(
        self,
        api_base: str,
        api_key: str,
        model: str,
        embedding_model: str,
        max_retries: int = 2,
    ) -> None:
        self._api_base = api_base.rstrip("/")
        self._api_key = api_key
        self._model = model
        self._embedding_model = embedding_model
        self._max_retries = max_retries

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self._client = httpx.Client(
            base_url=self._api_base,
            headers=headers,
            timeout=httpx.Timeout(120.0),
        )
        self._async_client: httpx.AsyncClient | None = None

    # ------------------------------------------------------------------
    # Chat (sync)
    # ------------------------------------------------------------------

    def _chat_with_retry(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.1,
    ) -> dict:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            payload["tools"] = tools

        resp = self._client.post("/chat/completions", json=payload)
        resp.raise_for_status()
        return resp.json()

    def chat(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.1,
    ) -> dict:
        """Synchronous chat completion with retry on rate limits."""
        retrier = retry(
            retry=retry_if_exception_type(httpx.HTTPStatusError),
            stop=stop_after_attempt(self._max_retries + 1),
            wait=wait_exponential(multiplier=1, min=1, max=30),
            before_sleep=lambda retry_state: logger.warning(
                "llm_retry",
                attempt=retry_state.attempt_number,
                exc=str(retry_state.outcome.exception()) if retry_state.outcome else "",
            ),
        )
        return retrier(self._chat_with_retry)(messages, tools, temperature)

    # ------------------------------------------------------------------
    # Chat (streaming)
    # ------------------------------------------------------------------

    async def chat_stream(
        self,
        messages: list[dict],
        tools: list[dict] | None = None,
        temperature: float = 0.1,
    ) -> AsyncIterator[dict]:
        """Streaming chat completion. Yields individual delta chunks."""
        if self._async_client is None:
            self._async_client = httpx.AsyncClient(
                base_url=self._api_base,
                headers=self._client.headers,
                timeout=httpx.Timeout(300.0),
            )

        payload: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "temperature": temperature,
            "stream": True,
        }
        if tools:
            payload["tools"] = tools

        async with self._async_client.stream("POST", "/chat/completions", json=payload) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    data = line.removeprefix("data: ")
                    if data == "[DONE]":
                        break
                    import json as _json

                    try:
                        chunk = _json.loads(data)
                        yield chunk
                    except _json.JSONDecodeError:
                        continue

    # ------------------------------------------------------------------
    # Embeddings
    # ------------------------------------------------------------------

    def embed(self, texts: list[str]) -> list[list[float]]:
        """Get embeddings for a list of texts using the configured embedding model."""
        payload = {
            "model": self._embedding_model,
            "input": texts,
        }

        retrier = retry(
            retry=retry_if_exception_type(httpx.HTTPStatusError),
            stop=stop_after_attempt(self._max_retries + 1),
            wait=wait_exponential(multiplier=1, min=1, max=30),
            before_sleep=lambda retry_state: logger.warning(
                "llm_embed_retry",
                attempt=retry_state.attempt_number,
            ),
        )

        @retrier
        def _embed() -> list[list[float]]:
            resp = self._client.post("/embeddings", json=payload)
            resp.raise_for_status()
            body = resp.json()
            # Sort by index to preserve input order
            data = sorted(body["data"], key=lambda d: d["index"])
            return [d["embedding"] for d in data]

        return _embed()

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the underlying HTTP client(s)."""
        self._client.close()
        if self._async_client is not None:
            # AsyncClient close is async, but we can schedule it with
            # a best-effort approach.
            import asyncio

            try:
                loop = asyncio.get_running_loop()
                loop.create_task(self._async_client.aclose())
            except RuntimeError:
                pass

    def __enter__(self) -> LLMClient:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


# ------------------------------------------------------------------
# Factory
# ------------------------------------------------------------------


def get_llm_client() -> LLMClient:  # noqa: D103
    settings = Settings()
    return LLMClient(
        api_base=settings.llm_api_base,
        api_key=settings.llm_api_key,
        model=settings.llm_model,
        embedding_model=settings.embedding_model,
        max_retries=settings.max_retries,
    )
