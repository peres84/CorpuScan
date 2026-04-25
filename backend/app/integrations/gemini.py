from __future__ import annotations

from google.genai import Client
from google.genai import types


class GeminiClient:
    def __init__(self, api_key: str) -> None:
        self._client = Client(api_key=api_key)

    async def generate(
        self,
        *,
        system: str,
        user: str,
        model: str = "gemini-2.5-pro",
        temperature: float = 0.2,
        response_mime_type: str | None = None,
    ) -> str:
        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=temperature,
            response_mime_type=response_mime_type,
        )
        response = await self._client.aio.models.generate_content(
            model=model,
            contents=user,
            config=config,
        )
        return (response.text or "").strip()
