from __future__ import annotations

import asyncio
from pathlib import Path

from app.agents.finance import run_finance_agent
from app.agents.hera import run_hera_agent
from app.agents.scripter import run_scripter_agent
from app.config import get_settings
from app.integrations.elevenlabs import (
    ElevenLabsClient,
    build_tts_input_and_scene_spans,
    compute_sentence_timings,
    map_sentence_timings_to_scenes,
)
from app.integrations.gemini import GeminiClient
from app.jobs import JobStore
from app.schemas import JobStep, SentenceTiming


async def run_pipeline(job_store: JobStore, job_id: str, source_text: str) -> None:
    try:
        settings = get_settings()
        job = job_store.get(job_id)
        if job is None:
            return
        job.source_text = source_text
        job_store.update_step(job_id, step=JobStep.INGEST, progress=10)
        job_store.update_step(job_id, step=JobStep.FINANCE, progress=20)

        gemini_client = GeminiClient(api_key=settings.gemini_api_key)
        qa_markdown = await run_finance_agent(source_text=source_text, gemini_client=gemini_client)
        job.qa_markdown = qa_markdown

        job_store.update_step(job_id, step=JobStep.SCRIPTER, progress=35)
        script = await run_scripter_agent(qa_markdown=qa_markdown, gemini_client=gemini_client)
        job.script = script.model_dump()

        job_store.update_step(job_id, step=JobStep.TTS, progress=50)
        tts_text, scene_spans = build_tts_input_and_scene_spans(script.scenes)
        elevenlabs = ElevenLabsClient(
            api_key=settings.elevenlabs_api_key,
            voice_id=settings.elevenlabs_voice_id,
        )
        audio_bytes, alignment = await elevenlabs.text_to_speech_with_timestamps(tts_text)
        characters = [str(ch) for ch in alignment.get("characters", [])]
        char_start_times = [float(v) for v in alignment.get("character_start_times_seconds", [])]
        char_end_times = [float(v) for v in alignment.get("character_end_times_seconds", [])]
        raw_sentence_timings = compute_sentence_timings(characters, char_start_times, char_end_times)
        sentence_timings = map_sentence_timings_to_scenes(raw_sentence_timings, scene_spans)

        out_dir = Path("/tmp") / job_id
        out_dir.mkdir(parents=True, exist_ok=True)
        audio_path = out_dir / "voice.mp3"
        audio_path.write_bytes(audio_bytes)

        job.audio_path = str(audio_path)
        job.sentence_timings = [timing.model_dump() for timing in sentence_timings]

        job_store.update_step(job_id, step=JobStep.HERA_PLAN, progress=65)
        timings_by_scene: list[list[SentenceTiming]] = [[] for _ in script.scenes]
        for timing in sentence_timings:
            timings_by_scene[timing.scene_index].append(timing)
        scene_specs = await asyncio.gather(
            *[
                run_hera_agent(
                    scene=scene,
                    sentence_timings_for_scene=timings,
                    gemini_client=gemini_client,
                )
                for scene, timings in zip(script.scenes, timings_by_scene, strict=True)
            ]
        )
        job.scene_specs = scene_specs
    except Exception as exc:
        job_store.set_error(job_id, str(exc))
