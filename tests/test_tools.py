from __future__ import annotations

import pytest
from unittest.mock import patch


class TestToolRegistry:
    def test_decorator_registers_tool(self):
        from src.tools.registry import TOOL_REGISTRY, tool

        @tool(name="test_hello", description="Test tool")
        async def hello(name: str) -> str:
            return f"Hello {name}"

        assert "test_hello" in TOOL_REGISTRY
        assert TOOL_REGISTRY["test_hello"]["description"] == "Test tool"

    def test_get_tool_schemas(self):
        from src.tools.registry import get_tool_schemas

        schemas = get_tool_schemas()
        assert isinstance(schemas, list)
        for s in schemas:
            assert s["type"] == "function"
            assert "function" in s
            assert "name" in s["function"]

    @pytest.mark.asyncio
    async def test_execute_tool_not_found(self):
        from src.tools.registry import execute_tool

        result = await execute_tool("nonexistent_tool", {})
        assert "not found" in result

    @pytest.mark.asyncio
    async def test_execute_tool_success(self):
        from src.tools.registry import TOOL_REGISTRY, tool

        @tool(name="test_echo", description="Echo")
        async def echo(message: str) -> str:
            return message

        from src.tools.registry import execute_tool
        result = await execute_tool("test_echo", {"message": "hi"})
        assert result == "hi"


class TestFileTools:
    @pytest.mark.asyncio
    async def test_read_file_not_found(self):
        from src.tools.file_tools import read_file

        result = await read_file("/nonexistent/path.txt")
        assert "not found" in result

    @pytest.mark.asyncio
    async def test_list_directory_not_found(self):
        from src.tools.file_tools import list_directory

        result = await list_directory("/nonexistent/dir")
        assert "not found" in result

    @pytest.mark.asyncio
    async def test_search_code_invalid_regex(self):
        from src.tools.file_tools import search_code

        result = await search_code(".", "[invalid")
        assert "invalid regex" in result


class TestExecTools:
    @pytest.mark.asyncio
    async def test_run_command_echo(self):
        from src.tools.exec_tools import run_command

        result = await run_command("echo hello")
        assert "hello" in result

    @pytest.mark.asyncio
    async def test_run_python(self):
        from src.tools.exec_tools import run_python

        result = await run_python("print('test output')")
        assert "test output" in result
