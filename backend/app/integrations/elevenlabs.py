from __future__ import annotations

import base64
import logging

import httpx

from app.schemas import Scene, SentenceTiming, SlideChunk

logger = logging.getLogger(__name__)


class ElevenLabsClient:
    def __init__(self, *, api_key: str, voice_id: str) -> None:
        self._api_key = api_key
        self._voice_id = voice_id
        self._base_url = "https://api.elevenlabs.io"

    async def text_to_speech_with_timestamps(self, text: str) -> tuple[bytes, dict[str, object]]:
        logger.info("elevenlabs tts started (chars=%d)", len(text))
        payload = {
            "text": text,
            "model_id": "eleven_multilingual_v2",
        }
        headers = {"xi-api-key": self._api_key}
        url = f"{self._base_url}/v1/text-to-speech/{self._voice_id}/with-timestamps"
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
        data = response.json()
        audio_base64 = data.get("audio_base64", "")
        alignment = data.get("alignment") or data.get("normalized_alignment") or {}
        audio_bytes = base64.b64decode(audio_base64)
        logger.info(
            "elevenlabs tts finished (audio_bytes=%d, alignment_chars=%d)",
            len(audio_bytes),
            len(alignment.get("characters", [])),
        )
        return audio_bytes, alignment

    async def generate_sound_effect(
        self, *, text: str, duration_seconds: float, prompt_influence: float = 0.5
    ) -> bytes:
        """Generate a sound effect via /v1/sound-generation. Returns raw MP3 bytes.
        duration_seconds must be in [0.5, 30] per the API spec.
        """
        logger.info(
            "elevenlabs sound effect started (duration=%.1fs, prompt_chars=%d)",
            duration_seconds,
            len(text),
        )
        payload = {
            "text": text,
            "duration_seconds": max(0.5, min(30.0, duration_seconds)),
            "prompt_influence": prompt_influence,
        }
        headers = {"xi-api-key": self._api_key, "Content-Type": "application/json"}
        url = f"{self._base_url}/v1/sound-generation"
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
        logger.info("elevenlabs sound effect finished (audio_bytes=%d)", len(response.content))
        return response.content


def build_tts_input_and_scene_spans(scenes: list[Scene]) -> tuple[str, list[tuple[int, int, int]]]:
    full_text_parts: list[str] = []
    spans: list[tuple[int, int, int]] = []
    cursor = 0
    for index, scene in enumerate(scenes):
        narration = scene.narration.strip()
        if narration and narration[-1] not in ".!?":
            narration = f"{narration}."
        if index > 0:
            full_text_parts.append(" ")
            cursor += 1
        start = cursor
        full_text_parts.append(narration)
        cursor += len(narration)
        spans.append((start, cursor, index))
    return "".join(full_text_parts), spans


def compute_sentence_timings(
    characters: list[str],
    char_start_times: list[float],
    char_end_times: list[float],
) -> list[dict[str, object]]:
    entries = list(zip(characters, char_start_times, char_end_times, strict=True))
    sentence_timings: list[dict[str, object]] = []
    sentence_chars: list[str] = []
    sentence_start: float | None = None
    sentence_end: float | None = None

    for ch, start, end in entries:
        if sentence_start is None and not ch.isspace():
            sentence_start = float(start)
        sentence_chars.append(ch)
        if not ch.isspace():
            sentence_end = float(end)
        if ch in ".!?":
            sentence = "".join(sentence_chars).strip()
            if sentence and sentence_start is not None and sentence_end is not None:
                sentence_timings.append(
                    {
                        "sentence": sentence,
                        "start_seconds": sentence_start,
                        "end_seconds": sentence_end,
                    }
                )
            sentence_chars = []
            sentence_start = None
            sentence_end = None

    trailing = "".join(sentence_chars).strip()
    if trailing and sentence_start is not None and sentence_end is not None:
        sentence_timings.append(
            {
                "sentence": trailing,
                "start_seconds": sentence_start,
                "end_seconds": sentence_end,
            }
        )
    return sentence_timings


def map_sentence_timings_to_scenes(
    sentence_timings: list[dict[str, object]],
    scene_spans: list[tuple[int, int, int]],
) -> list[SentenceTiming]:
    mapped: list[SentenceTiming] = []
    cursor = 0
    for timing in sentence_timings:
        sentence_text = str(timing["sentence"]).strip()
        sentence_start_offset = cursor
        located = False
        for scene_start, scene_end, scene_index in scene_spans:
            if scene_start <= sentence_start_offset < scene_end:
                mapped.append(
                    SentenceTiming(
                        scene_index=scene_index,
                        sentence=sentence_text,
                        start_seconds=float(timing["start_seconds"]),
                        end_seconds=float(timing["end_seconds"]),
                    )
                )
                located = True
                break
        if not located:
            fallback_scene = scene_spans[-1][2] if scene_spans else 0
            mapped.append(
                SentenceTiming(
                    scene_index=fallback_scene,
                    sentence=sentence_text,
                    start_seconds=float(timing["start_seconds"]),
                    end_seconds=float(timing["end_seconds"]),
                )
            )
        cursor += len(sentence_text) + 1
    return mapped


def compute_slide_chunks_for_scene(
    *,
    characters: list[str],
    char_start_times: list[float],
    char_end_times: list[float],
    scene_char_start: int,
    scene_char_end: int,
    max_chars: int = 80,
    min_chars: int = 30,
) -> list[SlideChunk]:
    """Group characters in [scene_char_start, scene_char_end) into ~max_chars
    slide chunks. Returned start/end seconds are RELATIVE to the start of
    the scene (so scene 2's chunks start at ~0s, not at the absolute audio
    offset of scene 2)."""
    if scene_char_start >= scene_char_end:
        return []
    seg_chars = characters[scene_char_start:scene_char_end]
    seg_starts = char_start_times[scene_char_start:scene_char_end]
    seg_ends = char_end_times[scene_char_start:scene_char_end]

    scene_audio_start: float | None = None
    for ch, s in zip(seg_chars, seg_starts):
        if not ch.isspace():
            scene_audio_start = float(s)
            break
    if scene_audio_start is None:
        return []

    chunks: list[SlideChunk] = []
    buf_chars: list[str] = []
    buf_start: float | None = None
    buf_end: float | None = None

    def _flush() -> None:
        nonlocal buf_chars, buf_start, buf_end
        text = "".join(buf_chars).strip()
        if text and buf_start is not None and buf_end is not None:
            chunks.append(
                SlideChunk(
                    text=text,
                    start_seconds=round(buf_start - scene_audio_start, 3),
                    end_seconds=round(buf_end - scene_audio_start, 3),
                    char_count=len(text),
                )
            )
        buf_chars = []
        buf_start = None
        buf_end = None

    for ch, s, e in zip(seg_chars, seg_starts, seg_ends):
        if buf_start is None and not ch.isspace():
            buf_start = float(s)
        buf_chars.append(ch)
        if not ch.isspace():
            buf_end = float(e)
        cur = "".join(buf_chars).strip()
        if (ch in ".!?" and len(cur) >= min_chars) or (
            len(cur) >= max_chars and ch.isspace()
        ):
            _flush()

    _flush()
    return chunks
