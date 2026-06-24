from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from src.api.dependencies import get_redis

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/{task_id}")
async def get_report(
    task_id: str,
    format: str = Query("json", description="Output format: json, markdown, or html"),
):
    """Get the analysis report for a completed task."""
    redis = await get_redis()
    task_data = await redis.get_json(f"task:{task_id}")
    if task_data is None:
        raise HTTPException(status_code=404, detail="Task not found")

    if task_data.get("status") != "completed":
        raise HTTPException(status_code=409, detail="Task not yet completed")

    # Get report from Redis
    report_data = await redis.get_json(f"report:{task_id}")
    if report_data is None:
        # Check if embedded in task
        report_data = task_data.get("final_report")
    if report_data is None:
        raise HTTPException(status_code=404, detail="Report not found for this task")

    if format == "markdown":
        md = _render_report_markdown(report_data)
        from fastapi.responses import PlainTextResponse
        return PlainTextResponse(content=md, media_type="text/markdown")

    elif format == "html":
        md = _render_report_markdown(report_data)
        from src.tools.report_tools import _markdown_to_html
        html = _markdown_to_html(md)
        page = f"""<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>{report_data.get('title', 'Report')}</title>
<style>body{{font-family:sans-serif;max-width:900px;margin:0 auto;padding:2rem;line-height:1.6}}
pre{{background:#f5f5f5;padding:1rem;border-radius:6px;overflow-x:auto}}
code{{background:#f0f0f0;padding:0.2em 0.4em;border-radius:3px}}
h1{{border-bottom:2px solid #eee}}h2{{border-bottom:1px solid #eee}}
blockquote{{border-left:3px solid #ccc;margin:0;padding-left:1rem;color:#555}}
</style></head><body>{html}</body></html>"""
        from fastapi.responses import HTMLResponse
        return HTMLResponse(content=page)

    return report_data


def _render_report_markdown(report: dict) -> str:
    """Render a report dict to markdown."""
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
                lines.append(f"- [{c.get('evidence_id', '')}] {c.get('text', '')}")
            lines.append("")

    lines.append(f"\n---\n*Report generated with review score: {report.get('review_score', 'N/A')}*")
    return "\n".join(lines)
