from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pytest

from app.integrations.llm_router import LLMRouter
from app.integrations.openai import OpenAIClient, OpenAIRateLimitError


class FakeOpenAIClient:
    """Mock OpenAI client for testing."""

    def __init__(self, *, responses: list[str | Exception] | None = None) -> None:
        self._responses: list[str | Exception] = responses or ["openai response"]
        self._call_count = 0
        self.calls: list[dict[str, object]] = []

    async def generate(
        self,
        *,
        system: str,
        user: str,
        model: str | None = None,
        temperature: float = 0.2,
        response_mime_type: str | None = None,
    ) -> str:
        self.calls.append(
            {
                "system": system,
                "user": user,
                "model": model,
                "temperature": temperature,
                "response_mime_type": response_mime_type,
            }
        )
        idx = min(self._call_count, len(self._responses) - 1)
        self._call_count += 1
        result = self._responses[idx]
        if isinstance(result, Exception):
            raise result
        return result


class FakeGeminiClient:
    """Mock Gemini client for testing."""

    def __init__(self, *, responses: list[str | Exception] | None = None) -> None:
        self._responses: list[str | Exception] = responses or ["gemini response"]
        self._call_count = 0
        self.calls: list[dict[str, object]] = []

    async def generate(
        self,
        *,
        system: str,
        user: str,
        model: str = "gemini-2.5-pro",
        temperature: float = 0.2,
        response_mime_type: str | None = None,
    ) -> str:
        self.calls.append(
            {
                "system": system,
                "user": user,
                "model": model,
                "temperature": temperature,
                "response_mime_type": response_mime_type,
            }
        )
        idx = min(self._call_count, len(self._responses) - 1)
        self._call_count += 1
        result = self._responses[idx]
        if isinstance(result, Exception):
            raise result
        return result


class TestLLMRouterCallsOpenAIFirst:
    @pytest.mark.asyncio
    async def test_openai_success_no_gemini_call(self) -> None:
        openai = FakeOpenAIClient(responses=["openai result"])
        gemini = FakeGeminiClient(responses=["gemini result"])
        router = LLMRouter(openai_client=openai, gemini_client=gemini)  # type: ignore[arg-type]

        result = await router.generate(system="sys", user="hello")

        assert result == "openai result"
        assert len(openai.calls) == 1
        assert len(gemini.calls) == 0

    @pytest.mark.asyncio
    async def test_openai_fails_falls_back_to_gemini(self) -> None:
        openai = FakeOpenAIClient(
            responses=[
                RuntimeError("connection error"),
                RuntimeError("still broken"),
            ]
        )
        gemini = FakeGeminiClient(responses=["gemini fallback"])
        router = LLMRouter(openai_client=openai, gemini_client=gemini)  # type: ignore[arg-type]

        result = await router.generate(system="sys", user="hello")

        assert result == "gemini fallback"
        assert len(openai.calls) == 2  # retried once
        assert len(gemini.calls) == 1

    @pytest.mark.asyncio
    async def test_openai_rate_limit_triggers_fallback(self) -> None:
        openai = FakeOpenAIClient(
            responses=[
                OpenAIRateLimitError("rate limited"),
                OpenAIRateLimitError("still rate limited"),
            ]
        )
        gemini = FakeGeminiClient(responses=["gemini after rate limit"])
        router = LLMRouter(openai_client=openai, gemini_client=gemini)  # type: ignore[arg-type]

        result = await router.generate(system="sys", user="hello")

        assert result == "gemini after rate limit"
        assert len(openai.calls) == 2
        assert len(gemini.calls) == 1


class TestLLMRouterGeminiOnly:
    @pytest.mark.asyncio
    async def test_gemini_only_when_no_openai(self) -> None:
        gemini = FakeGeminiClient(responses=["gemini only"])
        router = LLMRouter(openai_client=None, gemini_client=gemini)  # type: ignore[arg-type]

        result = await router.generate(system="sys", user="hello")

        assert result == "gemini only"
        assert len(gemini.calls) == 1


class TestLLMRouterNoClients:
    def test_raises_if_no_clients(self) -> None:
        with pytest.raises(RuntimeError, match="at least one LLM client"):
            LLMRouter(openai_client=None, gemini_client=None)


class TestOpenAIClientValidation:
    def test_placeholder_key_raises(self) -> None:
        with pytest.raises(RuntimeError, match="OpenAI API key is missing"):
            OpenAIClient(api_key="")

    def test_placeholder_key_raises_for_known_placeholder(self) -> None:
        with pytest.raises(RuntimeError, match="OpenAI API key is missing"):
            OpenAIClient(api_key="key_here")


class TestOpenAIClientRetries:
    @pytest.mark.asyncio
    async def test_router_retries_before_fallback(self) -> None:
        """Verify the router retries OpenAI before falling back."""
        openai = FakeOpenAIClient(
            responses=[
                RuntimeError("transient"),
                "recovered",
            ]
        )
        gemini = FakeGeminiClient(responses=["should not be called"])
        router = LLMRouter(openai_client=openai, gemini_client=gemini)  # type: ignore[arg-type]

        result = await router.generate(system="sys", user="hello")

        assert result == "recovered"
        assert len(openai.calls) == 2
        assert len(gemini.calls) == 0
