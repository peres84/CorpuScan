from __future__ import annotations

import base64

import httpx

from app.schemas import Scene, SentenceTiming


class ElevenLabsClient:
    def __init__(self, *, api_key: str, voice_id: str) -> None:
        self._api_key = api_key
        self._voice_id = voice_id
        self._base_url = "https://api.elevenlabs.io"

    async def text_to_speech_with_timestamps(self, text: str) -> tuple[bytes, dict[str, object]]:
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
        return base64.b64decode(audio_base64), alignment


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
