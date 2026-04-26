from __future__ import annotations

from app.agents._prompts import load_prompt
from app.integrations.gemini import GeminiClient
from app.schemas import Script


async def run_scripter_agent(*, qa_markdown: str, gemini_client: GeminiClient) -> Script:
    prompt = load_prompt("scripter")
    user = prompt.user_template.format(qa_markdown=qa_markdown)
    response_text = await gemini_client.generate(
        system=prompt.system,
        user=user,
        model=prompt.model,
        temperature=prompt.temperature,
        response_mime_type=prompt.response_mime_type,
    )
    return Script.model_validate_json(response_text)
