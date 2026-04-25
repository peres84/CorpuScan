from __future__ import annotations

from pydantic import BaseModel

import httpx


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
        payload = {"api_key": self._api_key, "query": query, "max_results": max_results}
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(f"{self._base_url}/search", json=payload)
            response.raise_for_status()
        data = response.json()
        return [TavilyResult.model_validate(item) for item in data.get("results", [])]

    async def extract(self, url: str) -> str:
        payload = {"api_key": self._api_key, "urls": [url], "extract_depth": "advanced"}
        async with httpx.AsyncClient(timeout=60) as client:
            response = await client.post(f"{self._base_url}/extract", json=payload)
            response.raise_for_status()
        data = response.json()
        results = data.get("results", [])
        if not results:
            return ""
        first = results[0]
        return str(first.get("raw_content") or first.get("content") or "").strip()
