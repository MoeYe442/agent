from __future__ import annotations

from pydantic import BaseModel, Field


class CodeIndexItem(BaseModel):
    name: str  # Symbol name (function, class, variable)
    kind: str  # "function", "class", "method", "variable", "module"
    file_path: str
    line_start: int
    line_end: int
    docstring: str = ""
    signature: str = ""  # Function/method signature
    parent_module: str = ""
    callers: list[str] = Field(default_factory=list)  # Names of calling symbols
    callees: list[str] = Field(default_factory=list)  # Names of called symbols
    dependencies: list[str] = Field(default_factory=list)  # Import dependencies


class ProjectIndex(BaseModel):
    project_name: str
    root_path: str
    language: str = "auto"
    files: list[str] = Field(default_factory=list)
    symbols: list[CodeIndexItem] = Field(default_factory=list)
    dependency_graph: dict[str, list[str]] = Field(default_factory=dict)
