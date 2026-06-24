from __future__ import annotations

try:
    from enum import StrEnum
except ImportError:
    from strenum import StrEnum  # type: ignore[import-not-found,no-redef]


class AgentRole(StrEnum):
    PLANNER = "planner"
    RESEARCHER = "researcher"
    CODE_READER = "code_reader"
    EXECUTOR = "executor"
    REVIEWER = "reviewer"
    REPORTER = "reporter"


class TaskPhase(StrEnum):
    PLANNING = "planning"
    RESEARCHING = "researching"
    READING = "reading"
    EXECUTING = "executing"
    REVIEWING = "reviewing"
    REPORTING = "reporting"
    COMPLETED = "completed"
    FAILED = "failed"


class SourceType(StrEnum):
    WEB_PAGE = "web_page"
    CODE_FILE = "code_file"
    GITHUB_REPO = "github_repo"
    DOCUMENT = "document"
    COMMAND_OUTPUT = "command_output"
    RAG_CHUNK = "rag_chunk"
