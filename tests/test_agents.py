from __future__ import annotations

import pytest


class TestPlanner:
    @pytest.mark.asyncio
    async def test_planner_creates_plan(self, sample_agent_state, mock_llm_client):
        from src.agents.planner import planner_node

        mock_llm_client.chat.return_value = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": '[{"step": 1, "title": "Analyze auth", "agent": "researcher", "goal": "Understand auth flow", "tools": ["read_file"]}]',
                }
            }]
        }

        result = await planner_node(sample_agent_state, mock_llm_client)
        assert "plan" in result
        assert len(result["plan"]) > 0
        assert result["plan"][0]["step"] == 1
        assert result["current_agent"] == "planner"


class TestReviewer:
    @pytest.mark.asyncio
    async def test_reviewer_passes_high_score(self, sample_agent_state, mock_llm_client):
        from src.agents.reviewer import reviewer_node

        mock_llm_client.chat.return_value = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": '{"score": 0.85, "summary": "Good research", "strengths": ["thorough"], "gaps": [], "needs_retry": false, "suggestions": ""}',
                }
            }]
        }

        result = await reviewer_node(sample_agent_state, mock_llm_client)
        assert result["review_score"] == 0.85
        assert result["phase"] == "reporting"

    @pytest.mark.asyncio
    async def test_reviewer_retries_low_score(self, sample_agent_state, mock_llm_client):
        from src.agents.reviewer import reviewer_node

        sample_agent_state["review_retries"] = 0
        mock_llm_client.chat.return_value = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": '{"score": 0.3, "summary": "Incomplete", "strengths": [], "gaps": ["missing analysis"], "needs_retry": true, "suggestions": "Deepen analysis"}',
                }
            }]
        }

        result = await reviewer_node(sample_agent_state, mock_llm_client)
        assert result["review_score"] == 0.3
        assert result["phase"] == "researching"
        assert result["review_retries"] == 1


class TestReporter:
    @pytest.mark.asyncio
    async def test_reporter_generates_report(self, sample_agent_state, mock_llm_client):
        from src.agents.reporter import reporter_node

        response = {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": '{"title": "Auth Analysis", "summary": "Complete analysis", "sections": [{"title": "Overview", "content": "## Overview\\n\\nTest overview.", "order": 1, "citations": [{"evidence_id": "ev1", "text": "source code", "source_path": "auth.py"}]}]}',
                }
            }]
        }
        mock_llm_client.chat.return_value = response

        result = await reporter_node(sample_agent_state, mock_llm_client)
        assert "final_report" in result
        assert result["phase"] == "completed"
        report = result["final_report"]
        assert len(report["sections"]) >= 1


class TestBaseFunctions:
    def test_estimate_tokens(self):
        from src.agents.base import estimate_tokens

        tokens = estimate_tokens("Hello world")
        assert tokens > 0

    def test_compress_context_no_op(self):
        from src.agents.base import compress_context

        msgs = [{"role": "user", "content": "short message"}]
        result = compress_context(msgs, max_tokens=100000)
        assert result == msgs

    def test_compress_context_reduces(self):
        from src.agents.base import compress_context

        msgs = [
            {"role": "system", "content": "You are helpful."},
        ] + [
            {"role": "user", "content": "x" * 10000}
            for _ in range(10)
        ]
        result = compress_context(msgs, max_tokens=500)
        assert len(result) < len(msgs)
