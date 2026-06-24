from __future__ import annotations

import shutil
import subprocess
import tempfile
from pathlib import Path

import structlog

logger = structlog.get_logger(__name__)

_CLONES_DIR = Path(tempfile.gettempdir()) / "code_research_clones"


def resolve_repo(repo_url: str, branch: str = "") -> Path:
    """Clone a GitHub repo shallowly or return a local path if it's already a directory.

    Returns the path to the cloned local repo.
    """
    url = repo_url.strip()

    # Local path
    local = Path(url)
    if local.exists() and local.is_dir():
        logger.info("repo_local_path", path=str(local))
        return local

    # GitHub URL
    _CLONES_DIR.mkdir(parents=True, exist_ok=True)
    repo_name = url.rstrip("/").split("/")[-1]
    if repo_name.endswith(".git"):
        repo_name = repo_name[:-4]
    dest = _CLONES_DIR / repo_name

    if dest.exists():
        shutil.rmtree(dest, ignore_errors=True)

    cmd = ["git", "clone", "--depth=1"]
    if branch:
        cmd.extend(["-b", branch])
    cmd.extend([url, str(dest)])

    logger.info("cloning_repo", url=url, dest=str(dest))
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if result.returncode != 0:
        raise RuntimeError(f"Clone failed: {result.stderr.strip()}")
    return dest
