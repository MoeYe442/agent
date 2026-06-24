from __future__ import annotations

import re
from pathlib import Path

from src.tools.registry import tool


@tool(
    name="render_markdown",
    description="Render markdown content and save to a file. Returns the file path.",
    parameters={
        "content": {"type": "string", "description": "Markdown content to render"},
        "output_path": {"type": "string", "description": "Output file path (.md)"},
    },
)
async def render_markdown(content: str, output_path: str) -> str:
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        p.write_text(content, encoding="utf-8")
    except Exception as exc:
        return f"Error writing markdown: {exc}"
    return f"Markdown saved to: {p}"


@tool(
    name="export_html",
    description="Convert markdown content to a basic HTML page and save it.",
    parameters={
        "content": {"type": "string", "description": "Markdown content to convert to HTML"},
        "output_path": {"type": "string", "description": "Output file path (.html)"},
        "title": {"type": "string", "description": "HTML page title"},
    },
)
async def export_html(content: str, output_path: str, title: str = "Analysis Report") -> str:
    html = _markdown_to_html(content)
    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_escape_html(title)}</title>
<style>
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
       max-width: 900px; margin: 0 auto; padding: 2rem; line-height: 1.6; color: #1a1a1a; }}
pre {{ background: #f5f5f5; padding: 1rem; border-radius: 6px; overflow-x: auto; }}
code {{ background: #f0f0f0; padding: 0.2em 0.4em; border-radius: 3px; font-size: 0.9em; }}
h1 {{ border-bottom: 2px solid #eee; padding-bottom: 0.5rem; }}
h2 {{ border-bottom: 1px solid #eee; padding-bottom: 0.3rem; }}
blockquote {{ border-left: 3px solid #ccc; margin: 0; padding-left: 1rem; color: #555; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #ddd; padding: 0.5rem; text-align: left; }}
th {{ background: #f5f5f5; }}
</style>
</head>
<body>
{html}
</body>
</html>"""
    p = Path(output_path)
    p.parent.mkdir(parents=True, exist_ok=True)
    try:
        p.write_text(page, encoding="utf-8")
    except Exception as exc:
        return f"Error writing HTML: {exc}"
    return f"HTML saved to: {p}"


def _markdown_to_html(md: str) -> str:
    """Basic markdown-to-HTML converter. For production use, prefer mistune or markdown-it-py."""
    out = _escape_html(md)

    # Code blocks (fenced)
    out = re.sub(r"```(\w*)\n(.*?)```", r"<pre><code class=\"language-\1\">\2</code></pre>", out, flags=re.DOTALL)
    # Inline code
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", out)
    # Headers
    out = re.sub(r"^#### (.+)$", r"<h4>\1</h4>", out, flags=re.MULTILINE)
    out = re.sub(r"^### (.+)$", r"<h3>\1</h3>", out, flags=re.MULTILINE)
    out = re.sub(r"^## (.+)$", r"<h2>\1</h2>", out, flags=re.MULTILINE)
    out = re.sub(r"^# (.+)$", r"<h1>\1</h1>", out, flags=re.MULTILINE)
    # Bold and italic
    out = re.sub(r"\*\*\*(.+?)\*\*\*", r"<strong><em>\1</em></strong>", out)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"\*(.+?)\*", r"<em>\1</em>", out)
    # Links
    out = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', out)
    # Images
    out = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", r'<img src="\2" alt="\1">', out)
    # Blockquotes
    out = re.sub(r"^> (.+)$", r"<blockquote>\1</blockquote>", out, flags=re.MULTILINE)
    # Horizontal rules
    out = re.sub(r"^---+$", "<hr>", out, flags=re.MULTILINE)
    # Unordered lists
    out = re.sub(r"^[*-] (.+)$", r"<li>\1</li>", out, flags=re.MULTILINE)
    out = re.sub(r"(<li>.*</li>)", r"<ul>\1</ul>", out, flags=re.DOTALL)
    # Paragraphs (blank-line separated blocks)
    paragraphs = out.split("\n\n")
    out = "\n\n".join(
        f"<p>{p}</p>" if not p.startswith("<") and p.strip() else p
        for p in paragraphs
    )
    # Clean up newlines
    out = out.replace("\n", "\n")
    return out


def _escape_html(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
