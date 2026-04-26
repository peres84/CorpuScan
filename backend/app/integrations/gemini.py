from __future__ import annotations

from google.genai import Client
from google.genai.errors import ClientError
from google.genai import types

_PLACEHOLDER_API_KEYS = {"", "key_here", "your_api_key", "api_key_here", "replace_me"}


def _is_placeholder_api_key(value: str) -> bool:
    return value.strip().lower() in _PLACEHOLDER_API_KEYS


class GeminiClient:
    def __init__(self, api_key: str) -> None:
        if _is_placeholder_api_key(api_key):
            raise RuntimeError(
                "Gemini API key is missing or still set to a placeholder in backend/.env. "
                "Set GEMINI_API_KEY to a real Google AI Studio key and restart the backend."
            )
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
        try:
            response = await self._client.aio.models.generate_content(
                model=model,
                contents=user,
                config=config,
            )
        except ClientError as exc:
            if exc.code == 400 and exc.status == "INVALID_ARGUMENT" and (
                "API key not valid" in (exc.message or "")
            ):
                raise RuntimeError(
                    "Gemini API key was rejected by Google. Replace GEMINI_API_KEY in "
                    "backend/.env with a valid Google AI Studio key, then restart the backend."
                ) from exc
            raise
        return (response.text or "").strip()
