from __future__ import annotations

import json
import re
from pathlib import Path

from app.integrations.gemini import GeminiClient
from app.schemas import Scene, SentenceTiming

REQUIRED_HERA_KEYS = {"duration", "elements", "background"}


def _load_hera_system_prompt() -> str:
    prompts_path = Path(__file__).resolve().parents[3] / "docs" / "agent-prompts.md"
    content = prompts_path.read_text(encoding="utf-8")
    match = re.search(
        r"## 3\. Hera Agent \(×4\).*?### System prompt\s+```(.*?)```",
        content,
        flags=re.DOTALL,
    )
    if match is None:
        raise ValueError("Could not locate Hera Agent system prompt in docs/agent-prompts.md")
    return match.group(1).strip()


async def run_hera_agent(
    *,
    scene: Scene,
    sentence_timings_for_scene: list[SentenceTiming],
    gemini_client: GeminiClient,
) -> dict[str, object]:
    system_prompt = _load_hera_system_prompt()
    timings_payload = [
        {"text": item.sentence, "start": item.start_seconds, "end": item.end_seconds}
        for item in sentence_timings_for_scene
    ]
    user_prompt = (
        f"Scene title: {scene.title}\n\n"
        f"Scene narration:\n{scene.narration}\n\n"
        f"Sentence-level timings:\n{json.dumps(timings_payload, indent=2)}"
    )
    response_text = await gemini_client.generate(
        system=system_prompt,
        user=user_prompt,
        model="gemini-2.5-pro",
        temperature=0.3,
        response_mime_type="application/json",
    )
    parsed = json.loads(response_text)
    if not isinstance(parsed, dict):
        raise ValueError("Hera response must be a JSON object.")
    validate_hera_spec(parsed)
    return parsed


def validate_hera_spec(spec: dict[str, object]) -> None:
    missing = [key for key in REQUIRED_HERA_KEYS if key not in spec]
    if missing:
        raise ValueError(f"Hera spec missing required top-level keys: {', '.join(missing)}")
