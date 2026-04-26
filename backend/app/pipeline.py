from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Awaitable, Callable, TypeVar

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
from app.logging_utils import stage_tag
from app.render import compose
from app.schemas import BrandingPalette, JobStep, PipelineContext, SlideChunk

logger = logging.getLogger(__name__)
T = TypeVar("T")

INTRO_TYPING_SOUND_PROMPT = (
    "vintage mechanical typewriter typing sound, rhythmic, no music, no voice"
)
INTRO_DURATION_SECONDS = 4


async def run_pipeline(
    job_store: JobStore,
    job_id: str,
    source_text: str,
    pipeline_context: PipelineContext,
) -> None:
    logger.info("%s [%s] pipeline started, source_text length=%d", stage_tag("job"), job_id, len(source_text))
    try:
        settings = get_settings()
        job = job_store.get(job_id)
        if job is None:
            return
        job.source_text = source_text
        job.pipeline_context = pipeline_context
        job_store.update_step(job_id, step=JobStep.INGEST, progress=10)
        job_store.update_step(job_id, step=JobStep.FINANCE, progress=20)
        logger.info("%s [%s] running finance agent", stage_tag("finance"), job_id)

        gemini_client = GeminiClient(api_key=settings.gemini_api_key)
        qa_markdown = await run_finance_agent(
            source_text=source_text,
            pipeline_context=pipeline_context,
            gemini_client=gemini_client,
        )
        job.qa_markdown = qa_markdown
        logger.info("%s [%s] finance done, qa_markdown length=%d", stage_tag("finance"), job_id, len(qa_markdown))

        job_store.update_step(job_id, step=JobStep.SCRIPTER, progress=35)
        logger.info("%s [%s] running scripter agent", stage_tag("scripter"), job_id)
        script = await run_scripter_agent(
            qa_markdown=qa_markdown,
            pipeline_context=pipeline_context,
            gemini_client=gemini_client,
        )
        job.script = script.model_dump()
        logger.info("%s [%s] scripter done, title=%r", stage_tag("scripter"), job_id, script.title)

        job_store.update_step(job_id, step=JobStep.TTS, progress=50)
        logger.info("%s [%s] running TTS + intro typing sound", stage_tag("tts"), job_id)
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
            "%s [%s] TTS done, voice=%d bytes, intro_sound=%d bytes, sentences=%d, slides=%s",
            stage_tag("tts"),
            job_id,
            len(audio_bytes),
            len(intro_sound_bytes),
            len(sentence_timings),
            [len(s) for s in slide_chunks_by_scene],
        )

        job_store.update_step(job_id, step=JobStep.HERA_PLAN, progress=65)
        logger.info("%s [%s] running hera agents x4 (slide-chunk-driven)", stage_tag("hera"), job_id)
        scene_specs = await asyncio.gather(
            *[
                run_hera_agent(
                    scene=scene,
                    slide_chunks_for_scene=chunks,
                    pipeline_context=pipeline_context,
                    gemini_client=gemini_client,
                )
                for scene, chunks in zip(script.scenes, slide_chunks_by_scene, strict=True)
            ]
        )
        branding = pipeline_context.branding or BrandingPalette(
            background="#F9FAFB",
            text="#111827",
            secondary="#374151",
            accent="#06B6D4",
        )
        intro_spec = build_intro_hera_spec(
            title=script.title,
            company_name=pipeline_context.company_name or "Unknown Company",
            period_label=pipeline_context.period_label or "Current Period",
            branding=branding,
            output_aspect_ratio=pipeline_context.output_aspect_ratio,
            duration_seconds=INTRO_DURATION_SECONDS,
        )
        job.scene_specs = scene_specs
        logger.info("%s [%s] hera plan done, %d scene specs + 1 intro", stage_tag("hera"), job_id, len(scene_specs))

        job_store.update_step(job_id, step=JobStep.HERA_RENDER, progress=75)
        all_specs = [intro_spec, *scene_specs]
        hera_client = HeraClient(api_key=settings.hera_api_key, base_url=settings.hera_base_url)
        clip_bytes_list = await render_hera_assets(
            job_store=job_store,
            job_id=job_id,
            hera_client=hera_client,
            all_specs=all_specs,
            timeout_seconds=settings.hera_render_timeout_seconds,
            retry_attempts=settings.hera_render_retry_attempts,
            poll_interval_seconds=settings.hera_poll_interval_seconds,
        )
        intro_clip_path = out_dir / "intro.mp4"
        intro_clip_path.write_bytes(clip_bytes_list[0])
        scene_clip_paths: list[str] = []
        for index, clip_bytes in enumerate(clip_bytes_list[1:]):
            clip_path = out_dir / f"clip_{index}.mp4"
            clip_path.write_bytes(clip_bytes)
            scene_clip_paths.append(str(clip_path))
        job.clip_paths = scene_clip_paths
        logger.info("%s [%s] all clips downloaded (intro + %d scenes)", stage_tag("hera"), job_id, len(scene_clip_paths))

        job_store.update_step(job_id, step=JobStep.COMPOSE, progress=92)
        logger.info("%s [%s] composing final video", stage_tag("compose"), job_id)
        final_video_path = out_dir / "final.mp4"
        compose(
            intro_clip_path=str(intro_clip_path),
            intro_sound_path=str(intro_sound_path),
            scene_clip_paths=scene_clip_paths,
            voice_path=str(audio_path),
            out_path=str(final_video_path),
        )
        job_store.set_done(job_id, video_url=f"/jobs/{job_id}/video")
        logger.info("%s [%s] pipeline complete", stage_tag("compose"), job_id)
    except Exception as exc:
        logger.exception("%s [%s] pipeline failed: %s", stage_tag("job"), job_id, exc)
        job_store.set_error(job_id, str(exc))


async def render_hera_assets(
    *,
    job_store: JobStore,
    job_id: str,
    hera_client: HeraClient,
    all_specs: list[dict[str, object]],
    timeout_seconds: int,
    retry_attempts: int,
    poll_interval_seconds: float,
) -> list[bytes]:
    total_scene_clips = max(0, len(all_specs) - 1)
    hera_video_ids = await asyncio.gather(
        *[
            with_retries(
                lambda spec=spec: hera_client.submit(spec),
                attempts=2,
                operation_name="submit Hera render",
            )
            for spec in all_specs
        ]
    )
    logger.info("%s [%s] hera videos submitted: %s", stage_tag("hera"), job_id, hera_video_ids)

    completed: dict[int, str] = {}
    total_renders = len(hera_video_ids)
    last_error: Exception | None = None

    for attempt in range(1, retry_attempts + 1):
        try:
            completed_scene_clips = sum(1 for clip_idx in completed if clip_idx > 0)
            progress = 75 + int((len(completed) / total_renders) * 15) if total_renders else 75
            job_store.update_hera_progress(
                job_id,
                completed_clips=completed_scene_clips,
                total_clips=total_scene_clips,
                attempt=attempt,
                max_attempts=retry_attempts,
                progress=min(progress, 90),
            )
            logger.info(
                "%s [%s] hera poll window %d/%d (completed=%d/%d)",
                stage_tag("hera"),
                job_id,
                attempt,
                retry_attempts,
                len(completed),
                total_renders,
            )
            await _poll_existing_hera_assets(
                job_store=job_store,
                job_id=job_id,
                hera_client=hera_client,
                hera_video_ids=hera_video_ids,
                completed=completed,
                total_scene_clips=total_scene_clips,
                timeout_seconds=timeout_seconds,
                poll_interval_seconds=poll_interval_seconds,
                attempt=attempt,
                max_attempts=retry_attempts,
            )
            break
        except TimeoutError as exc:
            last_error = exc
            logger.warning(
                "%s [%s] hera poll window %d/%d timed out; keeping existing video ids and continuing",
                stage_tag("hera"),
                job_id,
                attempt,
                retry_attempts,
            )
            if attempt == retry_attempts:
                break
        except Exception as exc:
            last_error = exc
            logger.warning(
                "%s [%s] hera polling failed on window %d/%d: %s",
                stage_tag("hera"),
                job_id,
                attempt,
                retry_attempts,
                exc,
            )
            if attempt == retry_attempts:
                break

    if len(completed) < total_renders:
        assert last_error is not None
        raise RuntimeError(
            f"Hera renders failed after {retry_attempts} polling window(s): {last_error}"
        ) from last_error

    return await asyncio.gather(
        *[
            with_retries(
                lambda url=completed[idx]: hera_client.download(url),
                attempts=2,
                operation_name="download Hera clip",
            )
            for idx in range(total_renders)
        ]
    )


async def _poll_existing_hera_assets(
    *,
    job_store: JobStore,
    job_id: str,
    hera_client: HeraClient,
    hera_video_ids: list[str],
    completed: dict[int, str],
    total_scene_clips: int,
    timeout_seconds: int,
    poll_interval_seconds: float,
    attempt: int,
    max_attempts: int,
) -> None:
    start_time = asyncio.get_running_loop().time()
    total_renders = len(hera_video_ids)
    while len(completed) < total_renders:
        if asyncio.get_running_loop().time() - start_time > timeout_seconds:
            raise TimeoutError(
                f"Timed out waiting for Hera renders after {timeout_seconds} seconds."
            )
        poll_results = await asyncio.gather(
            *[
                with_retries(
                    lambda video_id=video_id: hera_client.poll(video_id),
                    attempts=2,
                    operation_name="poll Hera render",
                )
                for video_id in hera_video_ids
            ]
        )
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
                completed_scene_clips = sum(1 for clip_idx in completed if clip_idx > 0)
                progress = 75 + int((len(completed) / total_renders) * 15)
                job_store.update_hera_progress(
                    job_id,
                    completed_clips=completed_scene_clips,
                    total_clips=total_scene_clips,
                    attempt=attempt,
                    max_attempts=max_attempts,
                    progress=min(progress, 90),
                )
                logger.info(
                    "%s [%s] clip %d ready on window %d (%d/%d scene clips)",
                    stage_tag("hera"),
                    job_id,
                    idx,
                    attempt,
                    completed_scene_clips,
                    total_scene_clips,
                )
        if len(completed) < total_renders:
            await asyncio.sleep(poll_interval_seconds)


async def with_retries(
    operation: Callable[[], Awaitable[T]],
    *,
    attempts: int,
    operation_name: str,
) -> T:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return await operation()
        except Exception as exc:
            last_error = exc
            if attempt == attempts:
                break
            logger.warning("%s %s failed on try %d/%d: %s", stage_tag("hera"), operation_name, attempt, attempts, exc)
            await asyncio.sleep(1)
    assert last_error is not None
    raise last_error
