#!/usr/bin/env python3
"""End-to-end demo: clone a repo, analyze it, and generate a report."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Settings
from src.infrastructure.llm import get_llm_client
from src.infrastructure.milvus import get_milvus_client
from src.infrastructure.redis import get_redis_client
from src.models.task import TaskSpec


async def main():
    settings = Settings()
    print(f"CodeResearch Agent Demo")
    print(f"LLM Model: {settings.llm_model}")
    print(f"Milvus: {settings.milvus_host}:{settings.milvus_port}")
    print()

    # Default demo task
    demo_query = "Analyze the architecture and key design patterns of this project"
    demo_repo = "https://github.com/psf/requests"

    if len(sys.argv) > 1:
        demo_query = sys.argv[1]
    if len(sys.argv) > 2:
        demo_repo = sys.argv[2]

    print(f"Query: {demo_query}")
    print(f"Repository: {demo_repo}")
    print()

    # Initialize clients
    print("Initializing infrastructure...")
    llm = get_llm_client()
    redis = get_redis_client()
    await redis.connect()

    # Create task spec
    spec = TaskSpec(
        query=demo_query,
        repo_urls=[demo_repo],
        max_depth=3,
        language="python",
    )

    # Run workflow
    from src.workflow.executor import WorkflowExecutor
    executor = WorkflowExecutor(
        llm_client=llm,
        redis_client=redis,
    )

    print("Submitting task...")
    record = await executor.run(spec)
    print(f"Task ID: {record.task_id}")
    print(f"Status: {record.status}")

    # Wait for completion
    print("Waiting for task completion...")
    for _ in range(60):
        await asyncio.sleep(2)
        task = await executor.get_task(record.task_id)
        if task:
            print(f"  Status: {task.status} | Phase: {task.phase}")
            if task.status in ("completed", "failed", "cancelled"):
                break
    else:
        print("Timed out waiting for task completion")

    # Get final result
    task = await executor.get_task(record.task_id)
    if task and task.status == "completed":
        print(f"\nTask completed!")
        print(f"Summary: {task.result_summary}")

        # Try to get the report
        report_data = await redis.get_json(f"report:{record.task_id}")
        if report_data:
            print(f"Report: {report_data.get('title', 'N/A')}")
            print(f"Sections: {len(report_data.get('sections', []))}")
    else:
        print(f"\nTask ended with status: {task.status if task else 'unknown'}")
        if task and task.error_message:
            print(f"Error: {task.error_message}")

    # Cleanup
    await redis.disconnect()
    print("\nDemo complete.")


if __name__ == "__main__":
    asyncio.run(main())
