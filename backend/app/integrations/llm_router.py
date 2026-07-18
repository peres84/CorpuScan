from __future__ import annotations

import asyncio
import logging

from app.integrations.gemini import GeminiClient
from app.integrations.openai import OpenAIClient
from app.logging_utils import stage_tag

logger = logging.getLogger(__name__)

# Max retries for transient failures before falling back
_MAX_RETRIES = 2
_RETRY_DELAY_SECONDS = 1.0


class LLMRouter:
    """Routes LLM calls to OpenAI first, falling back to Gemini on failure.

    Both clients expose the same `generate()` interface:
        generate(system=..., user=..., model=..., temperature=..., response_mime_type=...)

    Fallback triggers: any exception from OpenAI (rate limits, timeouts, errors).
    """

    def __init__(
        self,
        *,
        openai_client: OpenAIClient | None = None,
        gemini_client: GeminiClient | None = None,
    ) -> None:
        self._openai = openai_client
        self._gemini = gemini_client
        if openai_client is None and gemini_client is None:
            raise RuntimeError(
                "LLMRouter requires at least one LLM client (OpenAI or Gemini)."
            )

    async def generate(
        self,
        *,
        system: str,
        user: str,
        model: str | None = None,
        temperature: float = 0.2,
        response_mime_type: str | None = None,
    ) -> str:
        """Try OpenAI first with retries, fall back to Gemini on failure."""
        if self._openai is not None:
            for attempt in range(1, _MAX_RETRIES + 1):
                try:
                    return await self._openai.generate(
                        system=system,
                        user=user,
                        model=model,
                        temperature=temperature,
                        response_mime_type=response_mime_type,
                    )
                except Exception as exc:
                    logger.warning(
                        "%s openai attempt %d/%d failed: %s",
                        stage_tag("llm_router"),
                        attempt,
                        _MAX_RETRIES,
                        exc,
                    )
                    if attempt < _MAX_RETRIES:
                        await asyncio.sleep(_RETRY_DELAY_SECONDS)

            # OpenAI exhausted — fall back to Gemini
            if self._gemini is not None:
                logger.info(
                    "%s falling back to Gemini after OpenAI failure",
                    stage_tag("llm_router"),
                )
                return await self._gemini.generate(
                    system=system,
                    user=user,
                    temperature=temperature,
                    response_mime_type=response_mime_type,
                )
            raise RuntimeError("OpenAI failed and no Gemini fallback configured.")

        # No OpenAI configured — use Gemini directly
        if self._gemini is not None:
            return await self._gemini.generate(
                system=system,
                user=user,
                temperature=temperature,
                response_mime_type=response_mime_type,
            )

        raise RuntimeError("No LLM client available.")
