from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import uuid4

from app.schemas import JobState, JobStep, JobStatus

logger = logging.getLogger(__name__)


@dataclass
class JobRecord:
    status: JobState
    step: JobStep
    progress: int
    error: str | None = None
    video_url: str | None = None
    source_text: str | None = None
    qa_markdown: str | None = None
    script: dict[str, object] | None = None
    audio_path: str | None = None
    sentence_timings: list[dict[str, object]] | None = None
    scene_specs: list[dict[str, object]] | None = None
    clip_paths: list[str] | None = None
    hera_completed_clips: int = 0
    hera_total_clips: int = 0
    hera_attempt: int = 0
    hera_max_attempts: int = 0

    def to_status(self) -> JobStatus:
        return JobStatus(
            status=self.status,
            step=self.step,
            progress=self.progress,
            error=self.error,
            video_url=self.video_url,
            hera_completed_clips=self.hera_completed_clips,
            hera_total_clips=self.hera_total_clips,
            hera_attempt=self.hera_attempt,
            hera_max_attempts=self.hera_max_attempts,
        )


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}

    def create(self) -> str:
        job_id = str(uuid4())
        self._jobs[job_id] = JobRecord(status=JobState.PENDING, step=JobStep.INGEST, progress=0)
        logger.info("[%s] job created", job_id)
        return job_id

    def get(self, job_id: str) -> JobRecord | None:
        return self._jobs.get(job_id)

    def reset(self) -> None:
        cleared_jobs = len(self._jobs)
        self._jobs.clear()
        logger.info("job store reset (%d jobs cleared)", cleared_jobs)

    def update_step(self, job_id: str, *, step: JobStep, progress: int) -> None:
        job = self._require_job(job_id)
        previous_step = job.step
        previous_progress = job.progress
        job.step = step
        job.progress = progress
        job.status = JobState.RUNNING
        if previous_step != step or previous_progress != progress:
            logger.info(
                "[%s] job step -> %s (%d%%)",
                job_id,
                step.value,
                progress,
            )

    def set_error(self, job_id: str, message: str) -> None:
        job = self._require_job(job_id)
        job.status = JobState.ERROR
        job.error = message
        logger.error("[%s] job failed: %s", job_id, message)

    def set_done(self, job_id: str, *, video_url: str) -> None:
        job = self._require_job(job_id)
        job.status = JobState.DONE
        job.step = JobStep.DONE
        job.progress = 100
        job.video_url = video_url
        logger.info("[%s] job done -> %s", job_id, video_url)

    def update_hera_progress(
        self,
        job_id: str,
        *,
        completed_clips: int,
        total_clips: int,
        attempt: int,
        max_attempts: int,
        progress: int | None = None,
    ) -> None:
        job = self._require_job(job_id)
        previous_completed = job.hera_completed_clips
        previous_attempt = job.hera_attempt
        job.step = JobStep.HERA_RENDER
        job.status = JobState.RUNNING
        job.hera_completed_clips = completed_clips
        job.hera_total_clips = total_clips
        job.hera_attempt = attempt
        job.hera_max_attempts = max_attempts
        if progress is not None:
            job.progress = progress
        if previous_completed != completed_clips or previous_attempt != attempt:
            logger.info(
                "[%s] hera progress -> %d/%d clips (attempt %d/%d, %d%%)",
                job_id,
                completed_clips,
                total_clips,
                attempt,
                max_attempts,
                job.progress,
            )

    def _require_job(self, job_id: str) -> JobRecord:
        job = self.get(job_id)
        if job is None:
            raise KeyError(f"Unknown job id: {job_id}")
        return job
