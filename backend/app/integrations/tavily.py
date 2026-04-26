from __future__ import annotations

import logging

from pydantic import BaseModel

import httpx

from app.logging_utils import stage_tag

logger = logging.getLogger(__name__)


class TavilyResult(BaseModel):
    title: str
    url: str
    content: str | None = None
    score: float | None = None


class TavilyClient:
    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._base_url = "https://api.tavily.com"

    async def search(self, query: str, max_results: int = 5) -> list[TavilyResult]:
        logger.info("%s tavily search started (query=%r, max_results=%d)", stage_tag("tavily"), query, max_results)
        payload = {"api_key": self._api_key, "query": query, "max_results": max_results}
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(f"{self._base_url}/search", json=payload)
            response.raise_for_status()
        data = response.json()
        results = [TavilyResult.model_validate(item) for item in data.get("results", [])]
        logger.info("%s tavily search finished (%d results)", stage_tag("tavily"), len(results))
        return results

    async def extract(self, url: str) -> str:
        logger.info("%s tavily extract started (url=%s)", stage_tag("tavily"), url)
        payload = {"api_key": self._api_key, "urls": [url], "extract_depth": "advanced"}
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(f"{self._base_url}/extract", json=payload)
            response.raise_for_status()
        data = response.json()
        results = data.get("results", [])
        if not results:
            logger.warning("%s tavily extract returned no results", stage_tag("tavily"))
            return ""
        first = results[0]
        content = str(first.get("raw_content") or first.get("content") or "").strip()
        logger.info("%s tavily extract finished (%d chars)", stage_tag("tavily"), len(content))
        return content
