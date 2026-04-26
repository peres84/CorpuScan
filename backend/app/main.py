from __future__ import annotations

import asyncio
import logging
import shutil
import time
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse

from app.config import get_settings
from app.integrations.tavily import TavilyClient
from app.jobs import JobStore
from app.pipeline import run_pipeline
from app.schemas import GenerateResponse, JobStatus, JobStep

logger = logging.getLogger(__name__)

settings = get_settings()
job_store = JobStore()
app = FastAPI(title="CorpuScan API")
REQUEST_TIMEOUT_SECONDS = 240
STALE_TMP_AGE_SECONDS = 30 * 60
TMP_ROOT = Path("/tmp")

logger.info("CORS origins: %s", settings.cors_origins_list)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_timeout_middleware(request: Request, call_next):
    logger.info("%s %s from %s", request.method, request.url.path, request.headers.get("origin", "unknown"))
    try:
        response = await asyncio.wait_for(call_next(request), timeout=REQUEST_TIMEOUT_SECONDS)
        logger.info("%s %s → %s", request.method, request.url.path, response.status_code)
        return response
    except TimeoutError:
        logger.error("Request timed out: %s %s", request.method, request.url.path)
        return JSONResponse(status_code=504, content={"detail": "Request timed out."})


@app.on_event("startup")
async def startup_cleanup() -> None:
    cleanup_stale_tmp_jobs()


@app.on_event("shutdown")
async def shutdown_cleanup() -> None:
    cleanup_stale_tmp_jobs()


@app.get("/health")
async def health() -> dict[str, bool]:
    return {"ok": True}


@app.post("/generate", response_model=GenerateResponse)
async def generate(
    file: UploadFile | None = File(default=None),
    url: str | None = Form(default=None),
    query: str | None = Form(default=None),
) -> GenerateResponse:
    provided_count = sum(1 for value in [file, url, query] if value)
    if provided_count != 1:
        raise HTTPException(status_code=400, detail="Provide exactly one input: file, url, or query.")

    source_text = await _resolve_source_text(file=file, url=url, query=query)
    if not source_text.strip():
        raise HTTPException(status_code=400, detail="Could not extract text from the provided source.")

    job_id = job_store.create()
    job_store.update_step(job_id, step=JobStep.INGEST, progress=10)
    asyncio.create_task(run_pipeline(job_store, job_id, source_text))
    return GenerateResponse(job_id=job_id)


@app.get("/jobs/{job_id}", response_model=JobStatus)
async def get_job(job_id: str) -> JobStatus:
    job = job_store.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job.to_status()


@app.get("/jobs/{job_id}/video")
async def get_job_video(job_id: str, download: int = 0) -> FileResponse:
    video_path = Path("/tmp") / job_id / "final.mp4"
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video not found.")
    headers: dict[str, str] = {}
    if download == 1:
        headers["Content-Disposition"] = f'attachment; filename="{job_id}.mp4"'
    return FileResponse(video_path, media_type="video/mp4", headers=headers)


async def _resolve_source_text(
    *, file: UploadFile | None, url: str | None, query: str | None
) -> str:
    if file is not None:
        from app.ingest import extract_pdf_text

        file_bytes = await file.read()
        return extract_pdf_text(file_bytes)

    tavily_client = TavilyClient(api_key=settings.tavily_api_key)
    if url:
        return await tavily_client.extract(url)
    if query:
        results = await tavily_client.search(query)
        if not results:
            raise HTTPException(status_code=404, detail="No search results found for the provided query.")
        return await tavily_client.extract(results[0].url)
    return ""


def cleanup_stale_tmp_jobs(now_ts: float | None = None) -> None:
    now = now_ts if now_ts is not None else time.time()
    if not TMP_ROOT.exists():
        return
    for child in TMP_ROOT.iterdir():
        if not child.is_dir():
            continue
        try:
            age_seconds = now - child.stat().st_mtime
            if age_seconds > STALE_TMP_AGE_SECONDS:
                shutil.rmtree(child, ignore_errors=True)
        except OSError:
            continue
