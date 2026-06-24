from __future__ import annotations

from fastapi import APIRouter

from src.tools.registry import TOOL_REGISTRY, get_tool_schemas

router = APIRouter(prefix="/tools", tags=["tools"])


@router.get("")
async def list_tools():
    """List all registered tools."""
    schemas = get_tool_schemas()
    tools = []
    for s in schemas:
        func = s.get("function", {})
        tools.append({
            "name": func.get("name", ""),
            "description": func.get("description", ""),
            "parameters": func.get("parameters", {}),
        })
    return {"tools": tools, "count": len(tools)}


@router.post("/register")
async def register_tool(tool_def: dict):
    """Register a new tool dynamically (MCP-style)."""
    name = tool_def.get("name", "")
    if not name:
        return {"error": "Tool name is required"}

    if name in TOOL_REGISTRY:
        return {"tool_name": name, "status": "already_registered"}

    # Register as a passthrough tool
    async def passthrough(**kwargs):
        return f"Tool '{name}' called with: {kwargs}"

    TOOL_REGISTRY[name] = {
        "name": name,
        "description": tool_def.get("description", ""),
        "parameters": tool_def.get("parameters", {"type": "object", "properties": {}}),
        "func": passthrough,
    }
    return {"tool_name": name, "status": "registered"}
