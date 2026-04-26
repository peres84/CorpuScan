from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from app.agents.finance import run_finance_agent
from app.agents.hera import build_intro_hera_spec, run_hera_agent
from app.agents.scripter import run_scripter_agent
from app.config import get_settings
from app.integrations.elevenlabs import (
    ElevenLabsClient,
    build_tts_input_and_scene_spans,
    compute_sentence_timings,
    compute_slide_chunks_for_scene,
    map_sentence_timings_to_scenes,
)
from app.integrations.gemini import GeminiClient
from app.integrations.hera import HeraClient
from app.jobs import JobStore
from app.render import compose
from app.schemas import JobStep, SlideChunk

logger = logging.getLogger(__name__)

INTRO_TYPING_SOUND_PROMPT = (
    "vintage mechanical typewriter typing sound, rhythmic, no music, no voice"
)
INTRO_DURATION_SECONDS = 4
HERA_RENDER_TIMEOUT_SECONDS = 240


async def run_pipeline(job_store: JobStore, job_id: str, source_text: str) -> None:
    logger.info("[%s] pipeline started, source_text length=%d", job_id, len(source_text))
    try:
        settings = get_settings()
        job = job_store.get(job_id)
        if job is None:
            return
        job.source_text = source_text
        job_store.update_step(job_id, step=JobStep.INGEST, progress=10)
        job_store.update_step(job_id, step=JobStep.FINANCE, progress=20)
        logger.info("[%s] running finance agent", job_id)

        gemini_client = GeminiClient(api_key=settings.gemini_api_key)
        qa_markdown = await run_finance_agent(source_text=source_text, gemini_client=gemini_client)
        job.qa_markdown = qa_markdown
        logger.info("[%s] finance done, qa_markdown length=%d", job_id, len(qa_markdown))

        job_store.update_step(job_id, step=JobStep.SCRIPTER, progress=35)
        logger.info("[%s] running scripter agent", job_id)
        script = await run_scripter_agent(qa_markdown=qa_markdown, gemini_client=gemini_client)
        job.script = script.model_dump()
        logger.info("[%s] scripter done, title=%r", job_id, script.title)

        job_store.update_step(job_id, step=JobStep.TTS, progress=50)
        logger.info("[%s] running TTS + intro typing sound", job_id)
        tts_text, scene_spans = build_tts_input_and_scene_spans(script.scenes)
        elevenlabs = ElevenLabsClient(
            api_key=settings.elevenlabs_api_key,
            voice_id=settings.elevenlabs_voice_id,
        )
        # Voice TTS and the intro typing sound are independent — fan out.
        tts_task = elevenlabs.text_to_speech_with_timestamps(tts_text)
        sound_task = elevenlabs.generate_sound_effect(
            text=INTRO_TYPING_SOUND_PROMPT,
            duration_seconds=INTRO_DURATION_SECONDS,
        )
        (audio_bytes, alignment), intro_sound_bytes = await asyncio.gather(tts_task, sound_task)

        characters = [str(ch) for ch in alignment.get("characters", [])]
        char_start_times = [float(v) for v in alignment.get("character_start_times_seconds", [])]
        char_end_times = [float(v) for v in alignment.get("character_end_times_seconds", [])]
        raw_sentence_timings = compute_sentence_timings(characters, char_start_times, char_end_times)
        sentence_timings = map_sentence_timings_to_scenes(raw_sentence_timings, scene_spans)

        # Slide chunks per scene — transcript-derived, scene-relative timings
        # that drive the bracketed beats in each Hera prompt.
        slide_chunks_by_scene: list[list[SlideChunk]] = []
        for scene_start, scene_end, _scene_index in scene_spans:
            chunks = compute_slide_chunks_for_scene(
                characters=characters,
                char_start_times=char_start_times,
                char_end_times=char_end_times,
                scene_char_start=scene_start,
                scene_char_end=scene_end,
            )
            slide_chunks_by_scene.append(chunks)

        out_dir = Path("/tmp") / job_id
        out_dir.mkdir(parents=True, exist_ok=True)
        audio_path = out_dir / "voice.mp3"
        audio_path.write_bytes(audio_bytes)
        intro_sound_path = out_dir / "intro_sound.mp3"
        intro_sound_path.write_bytes(intro_sound_bytes)

        job.audio_path = str(audio_path)
        job.sentence_timings = [t.model_dump() for t in sentence_timings]
        logger.info(
            "[%s] TTS done, voice=%d bytes, intro_sound=%d bytes, sentences=%d, slides=%s",
            job_id,
            len(audio_bytes),
            len(intro_sound_bytes),
            len(sentence_timings),
            [len(s) for s in slide_chunks_by_scene],
        )

        job_store.update_step(job_id, step=JobStep.HERA_PLAN, progress=65)
        logger.info("[%s] running hera agents x4 (slide-chunk-driven)", job_id)
        scene_specs = await asyncio.gather(
            *[
                run_hera_agent(
                    scene=scene,
                    slide_chunks_for_scene=chunks,
                    gemini_client=gemini_client,
                )
                for scene, chunks in zip(script.scenes, slide_chunks_by_scene, strict=True)
            ]
        )
        intro_spec = build_intro_hera_spec(
            title=script.title, duration_seconds=INTRO_DURATION_SECONDS
        )
        job.scene_specs = scene_specs
        logger.info("[%s] hera plan done, %d scene specs + 1 intro", job_id, len(scene_specs))

        job_store.update_step(job_id, step=JobStep.HERA_RENDER, progress=75)
        # Submit intro + 4 scene clips in parallel. Index 0 = intro,
        # indices 1..4 = scenes 0..3.
        all_specs = [intro_spec, *scene_specs]
        hera_client = HeraClient(api_key=settings.hera_api_key, base_url=settings.hera_base_url)
        hera_video_ids = await asyncio.gather(*[hera_client.submit(spec) for spec in all_specs])
        logger.info("[%s] hera videos submitted: %s", job_id, hera_video_ids)

        completed: dict[int, str] = {}
        start_time = asyncio.get_running_loop().time()
        while len(completed) < len(hera_video_ids):
            if asyncio.get_running_loop().time() - start_time > HERA_RENDER_TIMEOUT_SECONDS:
                raise TimeoutError("Timed out waiting for Hera renders.")
            poll_results = await asyncio.gather(*[hera_client.poll(vid) for vid in hera_video_ids])
            for idx, result in enumerate(poll_results):
                if idx in completed:
                    continue
                status = str(result.get("status", "")).lower()
                file_url = result.get("file_url")
                if status == "failed":
                    raise RuntimeError(
                        f"Hera render {idx} failed: {result.get('error') or 'unknown error'}"
                    )
                if status == "success" and isinstance(file_url, str):
                    completed[idx] = file_url
                    progress = 75 + int((len(completed) / len(hera_video_ids)) * 15)
                    job_store.update_step(job_id, step=JobStep.HERA_RENDER, progress=min(progress, 90))
                    logger.info(
                        "[%s] clip %d ready (%d/%d)",
                        job_id,
                        idx,
                        len(completed),
                        len(hera_video_ids),
                    )
            if len(completed) < len(hera_video_ids):
                await asyncio.sleep(3)

        # Download all clips. Preserve order: intro first, then scenes 0..3.
        clip_bytes_list = await asyncio.gather(
            *[hera_client.download(completed[idx]) for idx in range(len(hera_video_ids))]
        )
        intro_clip_path = out_dir / "intro.mp4"
        intro_clip_path.write_bytes(clip_bytes_list[0])
        scene_clip_paths: list[str] = []
        for index, clip_bytes in enumerate(clip_bytes_list[1:]):
            clip_path = out_dir / f"clip_{index}.mp4"
            clip_path.write_bytes(clip_bytes)
            scene_clip_paths.append(str(clip_path))
        job.clip_paths = scene_clip_paths
        logger.info("[%s] all clips downloaded (intro + %d scenes)", job_id, len(scene_clip_paths))

        job_store.update_step(job_id, step=JobStep.COMPOSE, progress=92)
        logger.info("[%s] composing final video", job_id)
        final_video_path = out_dir / "final.mp4"
        compose(
            intro_clip_path=str(intro_clip_path),
            intro_sound_path=str(intro_sound_path),
            scene_clip_paths=scene_clip_paths,
            voice_path=str(audio_path),
            out_path=str(final_video_path),
        )
        job_store.set_done(job_id, video_url=f"/jobs/{job_id}/video")
        logger.info("[%s] pipeline complete", job_id)
    except Exception as exc:
        logger.exception("[%s] pipeline failed: %s", job_id, exc)
        job_store.set_error(job_id, str(exc))
