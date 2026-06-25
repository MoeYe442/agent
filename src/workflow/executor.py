from __future__ import annotations

import asyncio
import json
import uuid
from datetime import datetime
from typing import Any, AsyncIterator

import structlog

from src.models.agent_state import AgentState
from src.models.task import TaskRecord, TaskSpec, TaskStatus
from src.models.tool_call import ToolCallRecord
from src.workflow.graph import compile_workflow

logger = structlog.get_logger(__name__)


class WorkflowExecutor:
    """Executes LangGraph workflows with Redis-backed task lifecycle and pub/sub events."""

    def __init__(
        self,
        llm_client: Any,
        redis_client: Any = None,
        rag_pipeline: Any = None,
    ) -> None:
        from src.infrastructure.memory_store import InMemoryStore
        self._llm = llm_client
        self._redis = redis_client or InMemoryStore()
        self._rag = rag_pipeline
        self._active_runs: dict[str, asyncio.Task] = {}
        self._cancel_events: dict[str, asyncio.Event] = {}

    async def run(self, task_spec: TaskSpec, task_id_override: str = "") -> TaskRecord:
        """Execute a workflow for the given TaskSpec.

        Returns a TaskRecord with the final status.
        """
        task_id = task_id_override or uuid.uuid4().hex
        task_record = TaskRecord(
            task_id=task_id,
            spec=task_spec,
            status=TaskStatus.QUEUED,
        )

        await self._persist_task(task_record)
        await self._publish_event(task_id, "task_queued", {"task_id": task_id})

        cancel_event = asyncio.Event()
        self._cancel_events[task_id] = cancel_event

        coro = self._run_workflow(task_id, task_spec, cancel_event)
        self._active_runs[task_id] = asyncio.create_task(coro)

        return task_record

    async def cancel(self, task_id: str) -> bool:
        """Cancel a running task."""
        event = self._cancel_events.get(task_id)
        if event is not None:
            event.set()
            await self._publish_event(task_id, "task_cancelled", {"task_id": task_id})
            return True
        return False

    async def get_task(self, task_id: str) -> TaskRecord | None:
        """Retrieve a task record from the store."""
        data = await self._redis.get_json(f"task:{task_id}")
        if data is None:
            return None
        return TaskRecord(**data)

    async def _run_workflow(
        self,
        task_id: str,
        task_spec: TaskSpec,
        cancel_event: asyncio.Event,
    ) -> None:
        """Internal method to execute the workflow graph."""
        try:
            await self._update_task_status(task_id, TaskStatus.RUNNING)
            await self._publish_event(task_id, "task_started", {"task_id": task_id})

            # Resolve repo path
            repo_path = ""
            if task_spec.repo_urls:
                from src.repo_analyzer.cloner import resolve_repo
                try:
                    repo_path = str(resolve_repo(task_spec.repo_urls[0]))
                except Exception as exc:
                    logger.warning("repo_clone_failed", error=str(exc))

            # Build project index if repo available
            project_index = None
            if repo_path:
                from pathlib import Path
                from src.repo_analyzer.jedi_analyzer import build_project_index
                try:
                    project_index = build_project_index(Path(repo_path), task_spec.target_files or None)
                except Exception as exc:
                    logger.warning("project_index_failed", error=str(exc))

            # Build BM25-only RAG pipeline if no RAG but repo available
            rag = self._rag
            if rag is None and repo_path:
                from pathlib import Path
                from src.rag.pipeline import RAGPipeline
                try:
                    rag = RAGPipeline(
                        milvus_client=None,
                        llm_client=self._llm,
                    )
                    py_files = list(Path(repo_path).rglob("*.py"))
                    # Limit to avoid overwhelming context
                    await rag.ingest_files([str(f) for f in py_files[:500]])
                    logger.info("bm25_index_built", repo=repo_path, files=min(len(py_files), 500))
                except Exception as exc:
                    logger.warning("bm25_build_failed", error=str(exc))

            # Compile and run
            compiled = compile_workflow(
                self._llm,
                rag,
                repo_path,
                project_index,
            )

            initial_state: AgentState = {
                "task_id": task_id,
                "task_spec": task_spec,
                "messages": [],
                "current_agent": "",
                "phase": "planning",
                "plan": [],
                "findings": [],
                "tool_log": [],
                "evidence": [],
                "project_index": project_index.model_dump() if project_index else None,
                "review_score": None,
                "review_retries": 0,
                "final_report": None,
                "errors": [],
                "checkpoint_data": {},
                "compressed_context": None,
                "human_approval_required": False,
            }

            # Run with timeout
            from src.config import Settings
            settings = Settings()
            timeout = settings.task_timeout_seconds

            try:
                result = await asyncio.wait_for(
                    compiled.ainvoke(initial_state, {"configurable": {"thread_id": task_id}}),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                await self._update_task_status(task_id, TaskStatus.FAILED, error=f"Task timed out after {timeout}s")
                return

            if cancel_event.is_set():
                await self._update_task_status(task_id, TaskStatus.CANCELLED)
                return

            # Extract result
            final_report = result.get("final_report")
            review_score = result.get("review_score")

            # Persist report to Redis
            if final_report and self._redis:
                await self._redis.set_json(f"report:{task_id}", final_report)

            # Also save evidence separately
            evidence = result.get("evidence", [])
            if evidence and self._redis:
                await self._redis.set_json(f"evidence:{task_id}", {"items": evidence})

            await self._update_task_status(
                task_id,
                TaskStatus.COMPLETED,
                result_summary=f"Completed with review score: {review_score}",
            )
            await self._publish_event(task_id, "task_completed", {
                "task_id": task_id,
                "review_score": review_score,
                "has_report": final_report is not None,
            })

        except Exception as exc:
            logger.exception("workflow_failed", task_id=task_id, error=str(exc))
            await self._update_task_status(task_id, TaskStatus.FAILED, error=str(exc))
        finally:
            self._active_runs.pop(task_id, None)
            self._cancel_events.pop(task_id, None)

    async def _persist_task(self, record: TaskRecord) -> None:
        await self._redis.set_json(f"task:{record.task_id}", record.model_dump())

    async def _update_task_status(
        self,
        task_id: str,
        status: TaskStatus,
        error: str = "",
        result_summary: str = "",
    ) -> None:
        data = await self._redis.get_json(f"task:{task_id}")
        if data:
            record = TaskRecord(**data)
            record.status = status
            record.updated_at = datetime.utcnow()
            if status == TaskStatus.COMPLETED:
                record.completed_at = datetime.utcnow()
            if error:
                record.error_message = error
            if result_summary:
                record.result_summary = result_summary
            await self._redis.set_json(f"task:{task_id}", record.model_dump())

    async def _publish_event(self, task_id: str, event_type: str, payload: dict) -> None:
        try:
            event = {"event": event_type, "task_id": task_id, "timestamp": datetime.utcnow().isoformat(), **payload}
            await self._redis.publish(f"task_events:{task_id}", json.dumps(event, default=str))
        except Exception as exc:
            logger.warning("pubsub_failed", error=str(exc))
