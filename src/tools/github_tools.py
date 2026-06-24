from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

from src.tools.registry import tool

_CLONES_DIR = Path(tempfile.gettempdir()) / "code_research_clones"


@tool(
    name="clone_repo",
    description="Shallow clone a GitHub repository to a local temp directory. Returns the local path.",
    parameters={
        "repo_url": {"type": "string", "description": "GitHub repository URL (e.g. https://github.com/user/repo)"},
        "branch": {"type": "string", "description": "Optional branch name (default: default branch)"},
    },
)
async def clone_repo(repo_url: str, branch: str = "") -> str:
    _CLONES_DIR.mkdir(parents=True, exist_ok=True)

    repo_name = repo_url.rstrip("/").split("/")[-1]
    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]
    dest = _CLONES_DIR / repo_name

    # Remove existing clone
    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)

    cmd = ["git", "clone", "--depth=1"]
    if branch:
        cmd.extend(["-b", branch])
    cmd.extend([repo_url, str(dest)])

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            return f"Error cloning repo: {result.stderr.strip()}"
    except subprocess.TimeoutExpired:
        return f"Error: clone timed out after 120s: {repo_url}"
    except FileNotFoundError:
        return "Error: git is not installed or not on PATH"

    # List top-level contents
    items = sorted(dest.iterdir())
    listing = "\n".join(f"  {i.name}{'/' if i.is_dir() else ''}" for i in items[:50])
    return f"Cloned to: {dest}\nTop-level contents:\n{listing}"


@tool(
    name="get_repo_info",
    description="Get basic metadata about a cloned repository (branch, commit, file count).",
    parameters={
        "repo_path": {"type": "string", "description": "Local path to cloned repository"},
    },
)
async def get_repo_info(repo_path: str) -> str:
    p = Path(repo_path)
    if not p.exists():
        return f"Error: path not found: {repo_path}"

    info_lines: list[str] = []
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, cwd=str(p), timeout=10,
        )
        info_lines.append(f"Branch: {r.stdout.strip()}")
    except Exception:
        pass

    try:
        r = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, cwd=str(p), timeout=10,
        )
        info_lines.append(f"Commit: {r.stdout.strip()[:12]}")
    except Exception:
        pass

    try:
        r = subprocess.run(
            ["git", "log", "-1", "--format=%ci"],
            capture_output=True, text=True, cwd=str(p), timeout=10,
        )
        info_lines.append(f"Last commit: {r.stdout.strip()}")
    except Exception:
        pass

    # Count files (excluding .git)
    file_count = 0
    for item in p.rglob("*"):
        if item.is_file() and ".git" not in item.parts:
            file_count += 1
    info_lines.append(f"Files: {file_count}")

    return "\n".join(info_lines)
