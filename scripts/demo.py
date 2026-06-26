#!/usr/bin/env python3
"""End-to-end demo: analyze a local repo and generate a Markdown report.

No Redis or Milvus required — uses InMemoryStore + BM25-only search.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Settings
from src.infrastructure.llm import get_llm_client
from src.infrastructure.memory_store import InMemoryStore
from src.models.task import TaskSpec


def render_report_markdown(report: dict) -> str:
    """Render a report dict to nicely formatted Markdown."""
    lines = [
        f"# {report.get('title', 'Analysis Report')}",
        "",
        report.get("summary", ""),
        "",
    ]
    for section in report.get("sections", []):
        lines.append(f"## {section.get('title', '')}")
        lines.append("")
        lines.append(section.get("content", ""))
        lines.append("")
        citations = section.get("citations", [])
        if citations:
            lines.append("**Sources:**")
            for c in citations:
                eid = c.get("evidence_id", "")
                text = c.get("text", "")
                sp = c.get("source_path", "")
                if sp:
                    lines.append(f"- [{eid}] {sp} — {text}")
                else:
                    lines.append(f"- [{eid}] {text}")
            lines.append("")

    lines.append(f"\n---\n*Report generated with review score: {report.get('review_score', 'N/A')}*")
    return "\n".join(lines)


async def main():
    parser = argparse.ArgumentParser(description="CodeResearch Agent Demo")
    parser.add_argument(
        "--repo-path",
        type=str,
        default="",
        help="Path to a local repository to analyze (default: current project)",
    )
    parser.add_argument(
        "--query",
        type=str,
        default="Analyze the architecture and key design patterns of this project",
        help="Research question to answer",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="Save report to this file (default: print to stdout only)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=600,
        help="Max seconds to wait for task completion",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="LLM API key (falls back to LLM_API_KEY env var or .env file)",
    )
    parser.add_argument(
        "--api-base",
        type=str,
        default=None,
        help="LLM API base URL (default: https://api.openai.com/v1)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="LLM model name (default: gpt-4o)",
    )
    args = parser.parse_args()

    repo_path = args.repo_path or str(Path(__file__).parent.parent.resolve())
    if not Path(repo_path).is_dir():
        print(f"Error: Not a valid directory: {repo_path}")
        sys.exit(1)

    settings = Settings()
    print(f"CodeResearch Agent Demo")
    print(f"LLM Model: {settings.llm_model}")
    print(f"Repository: {repo_path}")
    print(f"Query: {args.query}")
    print()

    # Initialize clients (no Redis/Milvus needed)
    print("Initializing...")
    llm = get_llm_client(
        api_key=args.api_key,
        api_base=args.api_base,
        model=args.model,
    )
    store = InMemoryStore()
    await store.connect()

    # Create task spec
    spec = TaskSpec(
        query=args.query,
        repo_urls=[repo_path],
        max_depth=3,
        language="python",
    )

    # Run workflow
    from src.workflow.executor import WorkflowExecutor
    executor = WorkflowExecutor(
        llm_client=llm,
        redis_client=store,
    )

    print("Submitting task...")
    record = await executor.run(spec)
    print(f"Task ID: {record.task_id}")
    print(f"Initial status: {record.status}")
    print()

    # Poll for completion
    print("Waiting for task completion...")
    completed = False
    for i in range(args.timeout // 2):
        await asyncio.sleep(2)
        task = await executor.get_task(record.task_id)
        if task:
            status = task.status.value if hasattr(task.status, 'value') else str(task.status)
            summary = getattr(task, 'result_summary', '') or ''
            print(f"  [{i*2+2}s] Status: {status}  {summary}")
            if task.status in ("completed", "failed", "cancelled"):
                completed = True
                break
    else:
        print("Timed out waiting for task completion")

    # Get final result
    task = await executor.get_task(record.task_id)
    if not task:
        print("Error: Task record not found")
        return

    status = task.status.value if hasattr(task.status, 'value') else str(task.status)
    if status == "completed":
        print(f"\nTask completed!")

        # Get report
        report_data = await store.get_json(f"report:{record.task_id}")
        if report_data:
            md = render_report_markdown(report_data)
            print()
            print(md)

            if args.output:
                Path(args.output).write_text(md, encoding="utf-8")
                print(f"\nReport saved to: {args.output}")
        else:
            print("No report found for this task")
    else:
        print(f"\nTask ended with status: {status}")
        if hasattr(task, 'error_message') and task.error_message:
            print(f"Error: {task.error_message}")

    await store.disconnect()
    print("\nDemo complete.")


if __name__ == "__main__":
    asyncio.run(main())
