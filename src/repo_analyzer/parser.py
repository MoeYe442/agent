from __future__ import annotations

import os
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)


def analyze_project_structure(root: Path, max_depth: int = 4) -> dict:
    """Walk the project tree and return a structured directory overview.

    Returns a dict with:
        - tree: list of file/directory paths (relative)
        - file_count: total files
        - dir_count: total directories
        - by_extension: dict mapping extension to count
    """
    root = Path(root)
    if not root.is_dir():
        return {"tree": [], "file_count": 0, "dir_count": 0, "by_extension": {}}

    tree: list[str] = []
    file_count = 0
    dir_count = 0
    by_extension: dict[str, int] = {}

    for dirpath, dirnames, filenames in os.walk(root):
        rel = Path(dirpath).relative_to(root)
        depth = len(rel.parts) if rel != Path(".") else 0
        if depth > max_depth:
            dirnames.clear()
            continue

        dirnames[:] = sorted(d for d in dirnames if not d.startswith(".") and d != ".git")

        for d in dirnames:
            tree.append(str(rel / d) + "/")
            dir_count += 1

        for f in sorted(filenames):
            if f.startswith("."):
                continue
            tree.append(str(rel / f))
            file_count += 1
            ext = Path(f).suffix.lower()
            by_extension[ext] = by_extension.get(ext, 0) + 1

    logger.info("project_structure_analyzed", files=file_count, dirs=dir_count)
    return {
        "tree": tree,
        "file_count": file_count,
        "dir_count": dir_count,
        "by_extension": by_extension,
    }


def extract_readme(root: Path) -> str:
    """Find and return the contents of the project README file."""
    root = Path(root)
    for name in ("README.md", "README.rst", "README.txt", "README", "readme.md"):
        candidate = root / name
        if candidate.exists():
            try:
                return candidate.read_text(encoding="utf-8", errors="replace")
            except Exception:
                pass
    return "(no README found)"
