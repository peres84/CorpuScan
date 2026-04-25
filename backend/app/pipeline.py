from __future__ import annotations

from app.agents.finance import run_finance_agent
from app.config import get_settings
from app.integrations.gemini import GeminiClient
from app.jobs import JobStore
from app.schemas import JobStep


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
    except Exception as exc:
        job_store.set_error(job_id, str(exc))
