from __future__ import annotations

import json
import math

from app.agents._prompts import load_prompt
from app.integrations.gemini import GeminiClient
from app.schemas import Scene, SlideChunk

ALLOWED_FORMATS = {"mp4", "prores", "webm", "gif"}
ALLOWED_ASPECT_RATIOS = {"16:9", "9:16", "1:1", "4:5"}
ALLOWED_FPS = {"24", "25", "30", "60"}
ALLOWED_RESOLUTIONS = {"360p", "480p", "720p", "1080p", "4k"}

INTRO_DURATION_SECONDS = 4
INTRO_TYPE_CADENCE_PER_CHAR = 0.06


async def run_hera_agent(
    *,
    scene: Scene,
    slide_chunks_for_scene: list[SlideChunk],
    gemini_client: GeminiClient,
) -> dict[str, object]:
    prompt = load_prompt("hera")
    chunks_payload = [
        {
            "index": idx,
            "text": chunk.text,
            "start": chunk.start_seconds,
            "end": chunk.end_seconds,
            "char_count": chunk.char_count,
        }
        for idx, chunk in enumerate(slide_chunks_for_scene)
    ]
    user = prompt.user_template.format(
        scene_title=scene.title,
        scene_narration=scene.narration,
        slide_chunks_json=json.dumps(chunks_payload, indent=2),
    )
    response_text = await gemini_client.generate(
        system=prompt.system,
        user=user,
        model=prompt.model,
        temperature=prompt.temperature,
        response_mime_type=prompt.response_mime_type,
    )
    parsed = json.loads(response_text)
    if not isinstance(parsed, dict):
        raise ValueError("Hera response must be a JSON object.")
    spec = _normalize_hera_spec(parsed, slide_chunks_for_scene)
    validate_hera_spec(spec)
    return spec


def _normalize_hera_spec(
    spec: dict[str, object], chunks: list[SlideChunk]
) -> dict[str, object]:
    """Backstop the model: clamp duration to scene bounds, force the single
    expected output config. Cheaper than a retry round-trip."""
    if chunks:
        max_end = max(c.end_seconds for c in chunks)
        spec["duration_seconds"] = max(1, min(60, math.ceil(max_end)))
    spec["outputs"] = [
        {"format": "mp4", "aspect_ratio": "16:9", "fps": "30", "resolution": "1080p"}
    ]
    return spec


def build_intro_hera_spec(
    *, title: str, duration_seconds: int = INTRO_DURATION_SECONDS
) -> dict[str, object]:
    """Deterministic Hera spec for the title-card intro. No LLM call needed —
    the prompt template is fixed; only the title text varies."""
    safe_title = title.strip().replace('"', "'") or "Briefing"
    type_in_seconds = round(min(3.0, len(safe_title) * INTRO_TYPE_CADENCE_PER_CHAR), 2)
    if type_in_seconds < 1.0:
        type_in_seconds = 1.0
    hold_start = type_in_seconds
    fade_start = round(duration_seconds - 0.3, 2)
    prompt_text = (
        f"A {duration_seconds}-second motion graphic on a solid #F9FAFB background, "
        f"1920x1080 at 30fps. Palette: #111827 (text), #06B6D4 (accent), "
        f"#F9FAFB (background). Typography: JetBrains Mono for the title. "
        f"Editorial restraint — no decorative imagery, no gradients, no shadows.\n\n"
        f'[from 0.0s to {type_in_seconds}s] typewriter typing animation of "{safe_title}", '
        f"centered (x=960 y=540), JetBrains Mono 96px in #111827. Type one character "
        f"every {INTRO_TYPE_CADENCE_PER_CHAR}s with a hard cursor cadence. A blinking "
        f'"|" cursor in #06B6D4 follows the last typed character (0.5s on, 0.5s off).\n\n'
        f"[from {hold_start}s to {fade_start}s] hold the typed text. Cursor continues "
        f"to blink. No other elements on screen.\n\n"
        f"[from {fade_start}s to {duration_seconds}.0s] fade the entire scene out over 0.30s "
        f"to a clean #F9FAFB background."
    )
    return {
        "prompt": prompt_text,
        "duration_seconds": duration_seconds,
        "outputs": [
            {"format": "mp4", "aspect_ratio": "16:9", "fps": "30", "resolution": "1080p"}
        ],
    }


def validate_hera_spec(spec: dict[str, object]) -> None:
    prompt_text = spec.get("prompt")
    if not isinstance(prompt_text, str) or not prompt_text.strip():
        raise ValueError("Hera spec missing non-empty 'prompt'.")

    duration = spec.get("duration_seconds")
    if not isinstance(duration, int) or not 1 <= duration <= 60:
        raise ValueError("Hera spec 'duration_seconds' must be int in [1, 60].")

    outputs = spec.get("outputs")
    if not isinstance(outputs, list) or not 1 <= len(outputs) <= 10:
        raise ValueError("Hera spec 'outputs' must be a list of 1–10 entries.")
    for idx, output in enumerate(outputs):
        if not isinstance(output, dict):
            raise ValueError(f"Hera output {idx} is not an object.")
        if output.get("format") not in ALLOWED_FORMATS:
            raise ValueError(f"Hera output {idx} format invalid.")
        if output.get("aspect_ratio") not in ALLOWED_ASPECT_RATIOS:
            raise ValueError(f"Hera output {idx} aspect_ratio invalid.")
        # Hera requires fps as a STRING ("30", not 30); enforce strictly.
        fps = output.get("fps")
        if not isinstance(fps, str) or fps not in ALLOWED_FPS:
            raise ValueError(
                f"Hera output {idx} fps must be a string in {sorted(ALLOWED_FPS)}."
            )
        if output.get("resolution") not in ALLOWED_RESOLUTIONS:
            raise ValueError(f"Hera output {idx} resolution invalid.")
