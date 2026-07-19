"""
MCP router — exposes tool listing and invocation endpoints.

The Investigation Agent uses these tools for external research.
"""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.mcp.registry import call_tool, list_tools

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mcp", tags=["mcp"])


class ToolCallRequest(BaseModel):
    name: str = Field(min_length=1)
    arguments: dict[str, object] = Field(default_factory=dict)


class ToolCallResponse(BaseModel):
    name: str
    result: dict[str, object]


@router.get("/tools")
async def get_tools() -> dict[str, object]:
    """List all registered MCP tools and their descriptions."""
    tools = list_tools()
    return {"count": len(tools), "tools": tools}


@router.post("/call", response_model=ToolCallResponse)
async def call_mcp_tool(request: ToolCallRequest) -> ToolCallResponse:
    """Invoke an MCP tool by name with arguments."""
    try:
        result = call_tool(request.name, **request.arguments)
        return ToolCallResponse(name=request.name, result=result)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("MCP tool call failed: %s", request.name)
        raise HTTPException(status_code=500, detail=f"Tool execution failed: {exc}") from exc
