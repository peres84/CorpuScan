from __future__ import annotations

import logging

import httpx

from app.logging_utils import stage_tag

logger = logging.getLogger(__name__)

_PLACEHOLDER_API_KEYS = {"", "key_here", "your_api_key", "api_key_here", "replace_me"}


def _is_placeholder_api_key(value: str) -> bool:
    return value.strip().lower() in _PLACEHOLDER_API_KEYS


class OpenAIClient:
    """Async OpenAI chat completions client matching the GeminiClient interface."""

    def __init__(self, api_key: str, model: str = "gpt-4o") -> None:
        if _is_placeholder_api_key(api_key):
            raise RuntimeError(
                "OpenAI API key is missing or still set to a placeholder in backend/.env. "
                "Set OPENAI_KEY to a real OpenAI key and restart the backend."
            )
        self._api_key = api_key
        self._default_model = model
        self._base_url = "https://api.openai.com/v1"

    async def generate(
        self,
        *,
        system: str,
        user: str,
        model: str | None = None,
        temperature: float = 0.2,
        response_mime_type: str | None = None,
    ) -> str:
        resolved_model = model or self._default_model
        logger.info(
            "%s openai generate started (model=%s, temperature=%.2f, user_chars=%d)",
            stage_tag("openai"),
            resolved_model,
            temperature,
            len(user),
        )

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]

        payload: dict[str, object] = {
            "model": resolved_model,
            "messages": messages,
            "temperature": temperature,
        }

        if response_mime_type == "application/json":
            payload["response_format"] = {"type": "json_object"}

        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{self._base_url}/chat/completions",
                json=payload,
                headers=headers,
            )
            if response.status_code == 429:
                retry_after = response.headers.get("retry-after", "unknown")
                logger.warning(
                    "%s openai rate limited (retry-after=%s)",
                    stage_tag("openai"),
                    retry_after,
                )
                raise OpenAIRateLimitError(
                    f"OpenAI rate limit hit (retry-after: {retry_after})"
                )
            response.raise_for_status()

        data = response.json()
        choices = data.get("choices", [])
        if not choices:
            raise RuntimeError("OpenAI returned no choices in response.")

        output = (choices[0].get("message", {}).get("content") or "").strip()
        logger.info(
            "%s openai generate finished (%d chars)", stage_tag("openai"), len(output)
        )
        return output


class OpenAIRateLimitError(RuntimeError):
    """Raised when OpenAI returns HTTP 429."""
