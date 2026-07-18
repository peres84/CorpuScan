from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger(__name__)

ToolFunction = Callable[..., dict[str, Any]]


@dataclass
class MCPTool:
    name: str
    description: str
    handler: ToolFunction
    parameters: dict[str, str] = field(default_factory=dict)


_REGISTRY: dict[str, MCPTool] = {}


def register_tool(
    name: str,
    description: str,
    handler: ToolFunction,
    parameters: dict[str, str] | None = None,
) -> None:
    """Register an MCP tool in the global registry."""
    _REGISTRY[name] = MCPTool(
        name=name,
        description=description,
        handler=handler,
        parameters=parameters or {},
    )
    logger.debug("MCP tool registered: %s", name)


def get_tool(name: str) -> MCPTool | None:
    """Get a registered tool by name."""
    return _REGISTRY.get(name)


def list_tools() -> list[dict[str, str]]:
    """List all registered MCP tools with their descriptions."""
    return [
        {"name": tool.name, "description": tool.description}
        for tool in _REGISTRY.values()
    ]


def call_tool(name: str, **kwargs: Any) -> dict[str, Any]:
    """Call a registered MCP tool by name."""
    tool = _REGISTRY.get(name)
    if tool is None:
        raise ValueError(f"MCP tool not found: {name}")
    return tool.handler(**kwargs)
