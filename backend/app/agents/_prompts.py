from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"


class PromptConfig(BaseModel):
    model: str
    temperature: float
    response_mime_type: str | None = None
    system: str
    user_template: str


@lru_cache(maxsize=None)
def load_prompt(name: str) -> PromptConfig:
    path = PROMPTS_DIR / f"{name}.yaml"
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return PromptConfig.model_validate(data)
