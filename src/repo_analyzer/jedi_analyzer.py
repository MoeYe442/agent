from __future__ import annotations

import os
from pathlib import Path

import structlog

from src.models.code_index import CodeIndexItem, ProjectIndex

logger = structlog.get_logger(__name__)

_IGNORE_DIRS = {".git", "__pycache__", ".venv", "venv", "node_modules", ".tox", ".eggs", "build", "dist"}


def build_project_index(root: Path, target_files: list[str] | None = None) -> ProjectIndex:
    """Build a ProjectIndex by statically analyzing Python files using Jedi.

    Args:
        root: Root path of the project
        target_files: Optional list of specific file paths (relative to root) to analyze.
                      If None, analyzes all .py files.

    Returns a ProjectIndex with all discovered symbols.
    """
    root = Path(root)
    project_name = root.name

    try:
        import jedi
    except ImportError:
        logger.warning("jedi_not_installed")
        return ProjectIndex(project_name=project_name, root_path=str(root))

    # Collect Python files
    py_files: list[Path] = []
    if target_files:
        for tf in target_files:
            fp = root / tf
            if fp.exists() and fp.suffix == ".py":
                py_files.append(fp)
    else:
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in _IGNORE_DIRS and not d.startswith(".")]
            for fname in filenames:
                if fname.endswith(".py"):
                    py_files.append(Path(dirpath) / fname)

    all_symbols: list[CodeIndexItem] = []
    all_files: list[str] = []
    dep_graph: dict[str, list[str]] = {}

    for fpath in py_files:
        try:
            source = fpath.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue

        rel_path = str(fpath.relative_to(root))
        all_files.append(rel_path)

        try:
            script = jedi.Script(source, path=str(fpath))
            names = script.get_names(all_scopes=True, definitions=True)
        except Exception:
            continue

        file_symbols: list[CodeIndexItem] = []
        for name in names:
            if name.type not in ("function", "class", "statement"):
                continue
            item = CodeIndexItem(
                name=name.name,
                kind=name.type,
                file_path=rel_path,
                line_start=name.line or 0,
                line_end=name.line or 0,
                docstring=name.docstring() or "",
                signature=name.description or "",
                parent_module=name.module_name or "",
            )
            # Resolve callers/callees via Jedi
            try:
                definitions = name.goto()
                for d in definitions:
                    if d.type in ("function", "class") and d.name != name.name:
                        item.callees.append(d.full_name or d.name)
            except Exception:
                pass

            all_symbols.append(item)
            file_symbols.append(item)

        # Build dependency edges for this file
        imports = []
        for sym in file_symbols:
            if sym.parent_module:
                imports.append(sym.parent_module)
        dep_graph[rel_path] = list(set(imports))

    logger.info(
        "project_index_built",
        project=project_name,
        files=len(all_files),
        symbols=len(all_symbols),
    )
    return ProjectIndex(
        project_name=project_name,
        root_path=str(root),
        language="python",
        files=all_files,
        symbols=all_symbols,
        dependency_graph=dep_graph,
    )


def analyze_call_chain(
    root: Path, symbol_name: str, max_depth: int = 3
) -> list[CodeIndexItem]:
    """Trace the call chain for a given symbol name within the project.

    Returns an ordered list of CodeIndexItems representing the call chain.
    """
    root = Path(root)
    try:
        import jedi
    except ImportError:
        return []

    chain: list[CodeIndexItem] = []
    seen: set[str] = set()

    def _trace(name: str, depth: int) -> None:
        if depth > max_depth or name in seen:
            return
        seen.add(name)

        # Search project files for the symbol
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if d not in _IGNORE_DIRS and not d.startswith(".")]
            for fname in filenames:
                if not fname.endswith(".py"):
                    continue
                fpath = Path(dirpath) / fname
                try:
                    source = fpath.read_text(encoding="utf-8", errors="replace")
                except Exception:
                    continue
                try:
                    script = jedi.Script(source, path=str(fpath))
                    infer = script.infer(column=0, line=1)
                    names = script.get_names(all_scopes=True, definitions=True)
                except Exception:
                    continue

                for n in names:
                    if n.name == name and n.type in ("function", "class"):
                        item = CodeIndexItem(
                            name=n.name,
                            kind=n.type,
                            file_path=str(fpath.relative_to(root)),
                            line_start=n.line or 0,
                            line_end=n.line or 0,
                            docstring=n.docstring() or "",
                            signature=n.description or "",
                            parent_module=n.module_name or "",
                        )
                        chain.append(item)
                        # Recurse into callees
                        try:
                            for d in n.goto():
                                if d.name != name:
                                    item.callees.append(d.full_name or d.name)
                                    _trace(d.name, depth + 1)
                        except Exception:
                            pass
                        return

    _trace(symbol_name, 1)
    return chain
