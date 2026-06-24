from __future__ import annotations

import os
import re
from pathlib import Path

from src.tools.registry import tool


@tool(
    name="read_file",
    description="Read the contents of a file at the given path. Returns the file content as text.",
    parameters={
        "path": {"type": "string", "description": "Absolute or relative path to the file"},
        "start_line": {"type": "integer", "description": "Optional 1-based start line (default 1)"},
        "end_line": {"type": "integer", "description": "Optional 1-based end line (inclusive)"},
    },
)
async def read_file(path: str, start_line: int = 1, end_line: int | None = None) -> str:
    p = Path(path)
    if not p.exists():
        return f"Error: file not found: {path}"
    if p.is_dir():
        return f"Error: path is a directory: {path}"
    try:
        content = p.read_text(encoding="utf-8", errors="replace")
    except Exception as exc:
        return f"Error reading file: {exc}"

    lines = content.split("\n")
    total = len(lines)
    start = max(1, start_line) - 1
    if end_line is None:
        end = total
    else:
        end = min(end_line, total)
    selected = lines[start:end]
    return "\n".join(selected)


@tool(
    name="list_directory",
    description="List files and subdirectories in a directory. Supports recursive listing up to a given depth.",
    parameters={
        "path": {"type": "string", "description": "Directory path to list"},
        "depth": {"type": "integer", "description": "Recursion depth (default 1)"},
        "pattern": {"type": "string", "description": "Optional glob pattern filter (e.g. '*.py')"},
    },
)
async def list_directory(path: str, depth: int = 1, pattern: str = "*") -> str:
    p = Path(path)
    if not p.exists():
        return f"Error: directory not found: {path}"
    if not p.is_dir():
        return f"Error: not a directory: {path}"

    results: list[str] = []
    max_depth = min(depth, 5)

    def _walk(current: Path, current_depth: int) -> None:
        if current_depth > max_depth:
            return
        try:
            entries = sorted(current.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
        except PermissionError:
            return
        for entry in entries:
            if entry.name.startswith("."):
                continue
            rel = entry.relative_to(p)
            prefix = "  " * (current_depth - 1)
            if entry.is_dir():
                results.append(f"{prefix}{rel}/")
                _walk(entry, current_depth + 1)
            elif pattern == "*" or entry.match(pattern):
                results.append(f"{prefix}{rel}")

    _walk(p, 1)
    if not results:
        return f"(empty directory: {path})"
    return "\n".join(results)


@tool(
    name="search_code",
    description="Search for a regex pattern in files within a directory. Returns matching lines with file paths and line numbers.",
    parameters={
        "directory": {"type": "string", "description": "Directory to search in"},
        "pattern": {"type": "string", "description": "Regex pattern to search for"},
        "file_glob": {"type": "string", "description": "File glob filter (e.g. '*.py', '*.{ts,js}')"},
        "max_results": {"type": "integer", "description": "Maximum results to return (default 50)"},
    },
)
async def search_code(
    directory: str, pattern: str, file_glob: str = "*", max_results: int = 50
) -> str:
    import fnmatch

    p = Path(directory)
    if not p.exists() or not p.is_dir():
        return f"Error: invalid directory: {directory}"

    try:
        regex = re.compile(pattern)
    except re.error as exc:
        return f"Error: invalid regex pattern: {exc}"

    results: list[str] = []
    for root, dirs, files in os.walk(p):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for fname in files:
            if not fnmatch.fnmatch(fname, file_glob):
                continue
            fpath = Path(root) / fname
            try:
                lines = fpath.read_text(encoding="utf-8", errors="replace").split("\n")
            except Exception:
                continue
            for lineno, line in enumerate(lines, 1):
                if regex.search(line):
                    rel = fpath.relative_to(p)
                    results.append(f"{rel}:{lineno}: {line.strip()}")
                    if len(results) >= max_results:
                        break
            if len(results) >= max_results:
                break
        if len(results) >= max_results:
            break

    if not results:
        return f"No matches found for pattern '{pattern}' in {directory}"
    return f"Found {len(results)} matches:\n" + "\n".join(results)
