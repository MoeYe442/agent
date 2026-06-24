from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_llm_client():
    """Mock LLMClient for testing."""
    client = MagicMock()
    client.chat.return_value = {
        "choices": [{
            "message": {
                "role": "assistant",
                "content": '{"title": "Test Report", "summary": "A test summary", "sections": [{"title": "Overview", "content": "Test content", "order": 1, "citations": []}]}',
            }
        }]
    }
    client.embed.return_value = [[0.1] * 384 for _ in range(5)]
    return client


@pytest.fixture
def mock_redis_client():
    """Mock RedisClient for testing."""
    client = MagicMock()
    client.connect = AsyncMock()
    client.disconnect = AsyncMock()
    client.health_check = AsyncMock(return_value=True)
    client.get_json = AsyncMock(return_value=None)
    client.set_json = AsyncMock()
    client.publish = AsyncMock(return_value=1)
    client.rpush = AsyncMock(return_value=1)
    client.brpoplpush = AsyncMock(return_value=None)
    client.exists = AsyncMock(return_value=False)
    client.client = MagicMock()
    return client


@pytest.fixture
def mock_milvus_client():
    """Mock MilvusClientWrapper for testing."""
    client = MagicMock()
    client._ensure_connection = MagicMock()
    client.init_collection = MagicMock()
    client.insert = MagicMock(return_value=["id1", "id2"])
    client.search = MagicMock(return_value=[
        {"id": "id1", "distance": 0.2, "score": 0.8, "text": "test code", "source_path": "test.py", "metadata": {}},
    ])
    return client


@pytest.fixture
def sample_task_spec():
    """Create a sample TaskSpec for testing."""
    from src.models.task import TaskSpec
    return TaskSpec(
        query="How does the authentication system work?",
        repo_urls=["https://github.com/example/test-repo"],
        target_files=["src/auth.py"],
        max_depth=3,
        language="python",
    )


@pytest.fixture
def sample_agent_state(sample_task_spec):
    """Create a sample AgentState for testing."""
    return {
        "task_id": "test-task-001",
        "task_spec": sample_task_spec,
        "messages": [],
        "current_agent": "",
        "phase": "planning",
        "plan": [],
        "findings": [],
        "tool_log": [],
        "evidence": [],
        "project_index": None,
        "review_score": None,
        "review_retries": 0,
        "final_report": None,
        "errors": [],
        "checkpoint_data": {},
        "compressed_context": None,
        "human_approval_required": False,
    }
