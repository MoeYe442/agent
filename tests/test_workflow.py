from __future__ import annotations

import pytest
from unittest.mock import MagicMock, patch


class TestGraphConstruction:
    def test_build_workflow_creates_graph(self, mock_llm_client):
        from src.workflow.graph import build_workflow

        graph = build_workflow(mock_llm_client)
        assert graph is not None

    def test_compile_workflow(self, mock_llm_client):
        from src.workflow.graph import compile_workflow

        compiled = compile_workflow(mock_llm_client)
        assert compiled is not None


class TestCheckpoint:
    @pytest.mark.asyncio
    async def test_save_checkpoint(self, mock_redis_client):
        from src.workflow.checkpoint import save_checkpoint

        state = {"task_id": "test-1", "phase": "planning", "plan": []}
        await save_checkpoint(state, mock_redis_client, "test-1")
        mock_redis_client.set_json.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_checkpoint(self, mock_redis_client):
        from src.workflow.checkpoint import load_checkpoint

        mock_redis_client.get_json.return_value = {"task_id": "test-1", "phase": "planning"}
        result = await load_checkpoint(mock_redis_client, "test-1")
        assert result is not None
        assert result["task_id"] == "test-1"

    @pytest.mark.asyncio
    async def test_load_checkpoint_none(self, mock_redis_client):
        from src.workflow.checkpoint import load_checkpoint

        mock_redis_client.get_json.return_value = None
        result = await load_checkpoint(mock_redis_client, "missing-task")
        assert result is None


class TestContextManager:
    def test_maybe_compress_under_threshold(self):
        from src.workflow.context_manager import ContextManager

        cm = ContextManager(threshold=100000)
        msgs = [{"role": "user", "content": "hello"}]
        result = cm.maybe_compress(msgs)
        assert result == msgs

    def test_maybe_compress_over_threshold(self):
        from src.workflow.context_manager import ContextManager

        cm = ContextManager(threshold=100)
        msgs = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": "x" * 5000},
            {"role": "assistant", "content": "y" * 5000},
            {"role": "user", "content": "recent message"},
        ]
        result = cm.maybe_compress(msgs)
        assert len(result) < len(msgs)
        # System message should be preserved
        assert result[0]["role"] == "system"


class TestTokenCounter:
    def test_count_tokens(self):
        from src.utils.token_counter import count_tokens

        tokens = count_tokens("Hello world")
        assert isinstance(tokens, int)
        assert tokens > 0

    def test_count_tokens_batch(self):
        from src.utils.token_counter import count_tokens_batch

        result = count_tokens_batch(["hello", "world", "longer text"])
        assert len(result) == 3
        assert all(isinstance(t, int) for t in result)
