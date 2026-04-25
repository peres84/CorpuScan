from __future__ import annotations

import re
from pathlib import Path

from app.integrations.gemini import GeminiClient
from app.schemas import Script


def _load_scripter_system_prompt() -> str:
    prompts_path = Path(__file__).resolve().parents[3] / "docs" / "agent-prompts.md"
    content = prompts_path.read_text(encoding="utf-8")
    match = re.search(
        r"## 2\. Scripter Agent.*?### System prompt\s+```(.*?)```",
        content,
        flags=re.DOTALL,
    )
    if match is None:
        raise ValueError("Could not locate Scripter Agent system prompt in docs/agent-prompts.md")
    return match.group(1).strip()


async def run_scripter_agent(*, qa_markdown: str, gemini_client: GeminiClient) -> Script:
    system_prompt = _load_scripter_system_prompt()
    user_prompt = f"Analyst findings:\n\n{qa_markdown}"
    response_text = await gemini_client.generate(
        system=system_prompt,
        user=user_prompt,
        model="gemini-2.5-pro",
        temperature=0.4,
        response_mime_type="application/json",
    )
    return Script.model_validate_json(response_text)
