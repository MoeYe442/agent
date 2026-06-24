from __future__ import annotations

import asyncio
import subprocess
import tempfile
from pathlib import Path

from src.tools.registry import tool


@tool(
    name="run_command",
    description="Execute a shell command in a subprocess. Returns stdout and stderr.",
    parameters={
        "command": {"type": "string", "description": "Shell command to execute"},
        "cwd": {"type": "string", "description": "Working directory for the command"},
        "timeout": {"type": "integer", "description": "Timeout in seconds (default 30)"},
    },
)
async def run_command(command: str, cwd: str = "", timeout: int = 30) -> str:
    try:
        proc = await asyncio.create_subprocess_shell(
            command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=cwd if cwd else None,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        return f"Error: command timed out after {timeout}s: {command}"
    except Exception as exc:
        return f"Error executing command: {exc}"

    parts: list[str] = []
    if stdout:
        parts.append(f"STDOUT:\n{stdout.decode('utf-8', errors='replace').strip()}")
    if stderr:
        parts.append(f"STDERR:\n{stderr.decode('utf-8', errors='replace').strip()}")
    if not parts:
        parts.append(f"(exit code: {proc.returncode}, no output)")
    return "\n".join(parts)


@tool(
    name="run_python",
    description="Execute a Python code snippet in a subprocess and return its output.",
    parameters={
        "code": {"type": "string", "description": "Python source code to execute"},
        "timeout": {"type": "integer", "description": "Timeout in seconds (default 15)"},
    },
)
async def run_python(code: str, timeout: int = 15) -> str:
    # Write code to a temp file for execution
    tmp = tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, encoding="utf-8")
    try:
        tmp.write(code)
        tmp.close()

        proc = await asyncio.create_subprocess_exec(
            "python", tmp.name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
    except asyncio.TimeoutError:
        return f"Error: Python execution timed out after {timeout}s"
    except FileNotFoundError:
        return "Error: python interpreter not found"
    except Exception as exc:
        return f"Error executing Python: {exc}"
    finally:
        Path(tmp.name).unlink(missing_ok=True)

    parts: list[str] = []
    if stdout:
        parts.append(stdout.decode("utf-8", errors="replace").strip())
    if stderr:
        parts.append(f"STDERR:\n{stderr.decode('utf-8', errors='replace').strip()}")
    return "\n".join(parts) if parts else "(no output)"
