from __future__ import annotations

import inspect
from collections.abc import Callable
from typing import Any

TOOL_REGISTRY: dict[str, dict[str, Any]] = {}


def tool(
    name: str | None = None,
    description: str = "",
    parameters: dict[str, Any] | None = None,
) -> Callable:
    """Decorator to register a function as a callable tool.

    Usage:
        @tool(name="read_file", description="Read a file", parameters={...})
        async def read_file(path: str) -> str: ...
    """
    def decorator(func: Callable) -> Callable:
        tool_name = name or func.__name__
        sig = inspect.signature(func)
        param_schema: dict[str, Any] = {
            "type": "object",
            "properties": {},
            "required": [],
        }
        if parameters:
            param_schema = {
                "type": "object",
                "properties": parameters,
                "required": list(parameters.keys()),
            }
        else:
            for pname, p in sig.parameters.items():
                if pname in ("self", "cls"):
                    continue
                param_schema["properties"][pname] = _infer_json_type(p)
                if p.default is inspect.Parameter.empty:
                    param_schema["required"].append(pname)

        TOOL_REGISTRY[tool_name] = {
            "name": tool_name,
            "description": description or (func.__doc__ or "").split("\n")[0],
            "parameters": param_schema,
            "func": func,
        }
        return func
    return decorator


def _infer_json_type(p: inspect.Parameter) -> dict[str, Any]:
    """Infer a JSON Schema type from a Python parameter annotation."""
    annotation = p.annotation if p.annotation is not inspect.Parameter.empty else str
    type_map = {
        str: "string",
        int: "integer",
        float: "number",
        bool: "boolean",
        list: "array",
        dict: "object",
    }
    json_type = type_map.get(annotation, "string")
    result: dict[str, Any] = {"type": json_type}
    if p.default is not inspect.Parameter.empty:
        result["default"] = p.default
    return result


def get_tool_schemas() -> list[dict[str, Any]]:
    """Return tool definitions in OpenAI function-calling format."""
    schemas = []
    for tdef in TOOL_REGISTRY.values():
        schemas.append({
            "type": "function",
            "function": {
                "name": tdef["name"],
                "description": tdef["description"],
                "parameters": tdef["parameters"],
            },
        })
    return schemas


async def execute_tool(name: str, arguments: dict[str, Any]) -> str:
    """Execute a registered tool by name and return its result as a string."""
    if name not in TOOL_REGISTRY:
        return f"Error: tool '{name}' not found"
    func = TOOL_REGISTRY[name]["func"]
    try:
        result = func(**arguments)
        if inspect.iscoroutine(result):
            result = await result
        if isinstance(result, str):
            return result
        import json
        return json.dumps(result, default=str, indent=2)
    except Exception as exc:
        return f"Tool '{name}' error: {exc}"
