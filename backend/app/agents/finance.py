from __future__ import annotations

from app.agents._prompts import load_prompt
from app.integrations.gemini import GeminiClient


async def run_finance_agent(*, source_text: str, gemini_client: GeminiClient) -> str:
    prompt = load_prompt("finance")
    user = prompt.user_template.format(source_text=source_text)
    return await gemini_client.generate(
        system=prompt.system,
        user=user,
        model=prompt.model,
        temperature=prompt.temperature,
        response_mime_type=prompt.response_mime_type,
    )
