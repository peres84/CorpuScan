"""
MCP-style wrappers for Tavily web tools.

Exposes web.search, web.extract as MCP tools that the Investigation Agent
can invoke to perform external research during an investigation.
"""

from __future__ import annotations

import logging
import os

import httpx

from app.mcp.registry import register_tool

logger = logging.getLogger(__name__)

_TAVILY_BASE_URL = "https://api.tavily.com"
_RATE_LIMIT_PER_MINUTE = 10
_TIMEOUT_SECONDS = 30
_MAX_EXTRACT_CHARS = 12000


def _get_api_key() -> str:
    key = os.environ.get("TAVILY_API_KEY", "").strip()
    if not key or key.lower() in (
        "key_here",
        "your_api_key",
        "api_key_here",
        "replace_me",
    ):
        raise RuntimeError("TAVILY_API_KEY is not configured")
    return key


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    return f"{text[: max_chars - 3]}..."


def web_search(query: str, max_results: int = 5) -> dict:
    """Run a Tavily search and return normalized results."""
    api_key = _get_api_key()
    payload = {
        "api_key": api_key,
        "query": query.strip(),
        "max_results": max_results,
        "search_depth": "basic",
    }

    with httpx.Client(timeout=_TIMEOUT_SECONDS, follow_redirects=False) as client:
        response = client.post(f"{_TAVILY_BASE_URL}/search", json=payload)
        response.raise_for_status()

    data = response.json()
    results = [
        {
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "snippet": (item.get("content") or "")[:500],
            "score": item.get("score"),
        }
        for item in data.get("results", [])
        if item.get("url")
    ]

    logger.info("MCP web.search: query=%r, results=%d", query, len(results))
    return {
        "query": data.get("query", query),
        "answer": data.get("answer"),
        "results": results,
    }


def web_extract(url: str) -> dict:
    """Extract cleaned content from an HTTPS URL."""
    if not url.lower().startswith("https://"):
        raise ValueError("Only https:// URLs are allowed for web.extract")

    api_key = _get_api_key()
    payload = {
        "api_key": api_key,
        "urls": [url],
        "extract_depth": "advanced",
    }

    with httpx.Client(timeout=60, follow_redirects=False) as client:
        response = client.post(f"{_TAVILY_BASE_URL}/extract", json=payload)
        response.raise_for_status()

    data = response.json()
    results = data.get("results", [])
    if not results:
        return {"url": url, "content": "", "title": ""}

    first = results[0]
    content = str(first.get("raw_content") or first.get("content") or "").strip()
    content = _truncate(content, _MAX_EXTRACT_CHARS)

    logger.info("MCP web.extract: url=%s, content_chars=%d", url, len(content))
    return {
        "url": url,
        "title": first.get("title", ""),
        "content": content,
    }


def register_tavily_tools() -> None:
    """Register Tavily MCP tools in the global registry."""
    register_tool(
        name="web.search",
        description="Search the web using Tavily. Returns titles, URLs, and snippets.",
        handler=web_search,
        parameters={
            "query": "Search query string",
            "max_results": "Max results (default 5)",
        },
    )
    register_tool(
        name="web.extract",
        description="Extract cleaned content from an HTTPS URL using Tavily.",
        handler=web_extract,
        parameters={"url": "HTTPS URL to extract content from"},
    )
