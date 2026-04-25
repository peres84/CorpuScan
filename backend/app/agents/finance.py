from __future__ import annotations

import re
from pathlib import Path

from app.integrations.gemini import GeminiClient


def _load_finance_system_prompt() -> str:
    prompts_path = Path(__file__).resolve().parents[3] / "docs" / "agent-prompts.md"
    content = prompts_path.read_text(encoding="utf-8")
    match = re.search(
        r"## 1\. Finance Agent.*?### System prompt\s+```(.*?)```",
        content,
        flags=re.DOTALL,
    )
    if match is None:
        raise ValueError("Could not locate Finance Agent system prompt in docs/agent-prompts.md")
    return match.group(1).strip()


async def run_finance_agent(*, source_text: str, gemini_client: GeminiClient) -> str:
    system_prompt = _load_finance_system_prompt()
    user_prompt = f"Source document text:\n\n<<<\n{source_text}\n>>>"
    return await gemini_client.generate(
        system=system_prompt,
        user=user_prompt,
        model="gemini-2.5-pro",
        temperature=0.2,
    )
