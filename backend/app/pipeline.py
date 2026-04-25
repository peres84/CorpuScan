from __future__ import annotations

from app.jobs import JobStore
from app.schemas import JobStep


async def run_pipeline(job_store: JobStore, job_id: str, source_text: str) -> None:
    try:
        job = job_store.get(job_id)
        if job is None:
            return
        job.source_text = source_text
        # Placeholder until downstream stages are implemented.
        job_store.update_step(job_id, step=JobStep.INGEST, progress=10)
    except Exception as exc:
        job_store.set_error(job_id, str(exc))
