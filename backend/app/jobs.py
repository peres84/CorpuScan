from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from app.schemas import JobState, JobStep, JobStatus


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

    def to_status(self) -> JobStatus:
        return JobStatus(
            status=self.status,
            step=self.step,
            progress=self.progress,
            error=self.error,
            video_url=self.video_url,
        )


class JobStore:
    def __init__(self) -> None:
        self._jobs: dict[str, JobRecord] = {}

    def create(self) -> str:
        job_id = str(uuid4())
        self._jobs[job_id] = JobRecord(status=JobState.PENDING, step=JobStep.INGEST, progress=0)
        return job_id

    def get(self, job_id: str) -> JobRecord | None:
        return self._jobs.get(job_id)

    def update_step(self, job_id: str, *, step: JobStep, progress: int) -> None:
        job = self._require_job(job_id)
        job.step = step
        job.progress = progress
        job.status = JobState.RUNNING

    def set_error(self, job_id: str, message: str) -> None:
        job = self._require_job(job_id)
        job.status = JobState.ERROR
        job.error = message

    def set_done(self, job_id: str, *, video_url: str) -> None:
        job = self._require_job(job_id)
        job.status = JobState.DONE
        job.step = JobStep.DONE
        job.progress = 100
        job.video_url = video_url

    def _require_job(self, job_id: str) -> JobRecord:
        job = self.get(job_id)
        if job is None:
            raise KeyError(f"Unknown job id: {job_id}")
        return job
