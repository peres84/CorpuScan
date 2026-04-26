from __future__ import annotations

import asyncio
import logging
import shutil
import time
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.config import get_settings
from app.integrations.tavily import TavilyClient
from app.jobs import JobStore
from app.pipeline import run_pipeline
from app.schemas import GenerateResponse, JobStatus, JobStep

logger = logging.getLogger(__name__)

settings = get_settings()
job_store = JobStore()
REQUEST_TIMEOUT_SECONDS = 240
STALE_TMP_AGE_SECONDS = 30 * 60
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
TMP_ROOT = Path("/tmp")


@asynccontextmanager
async def lifespan(_: FastAPI):
    cleanup_stale_tmp_jobs()
    yield
    cleanup_stale_tmp_jobs()


app = FastAPI(title="CorpuScan API", lifespan=lifespan)

_origins = settings.cors_origins_list
# CORS spec: credentials cannot be combined with wildcard origins.
_allow_credentials = "*" not in _origins
logger.info("CORS origins: %s (credentials=%s)", _origins, _allow_credentials)

app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=_allow_credentials,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_timeout_middleware(request: Request, call_next):
    is_poll = request.method == "GET" and request.url.path.startswith("/jobs/") and not request.url.path.endswith(
        "/video"
    )
    if not is_poll:
        logger.info(
            "%s %s from %s",
            request.method,
            request.url.path,
            request.headers.get("origin", "unknown"),
        )
    try:
        response = await asyncio.wait_for(call_next(request), timeout=REQUEST_TIMEOUT_SECONDS)
    except TimeoutError:
        logger.error("Request timed out: %s %s", request.method, request.url.path)
        return JSONResponse(status_code=504, content={"detail": "Request timed out."})
    if not is_poll:
        logger.info("%s %s → %s", request.method, request.url.path, response.status_code)
    return response


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
    safe_id = _validate_job_id(job_id)
    job = job_store.get(safe_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    return job.to_status()


@app.get("/jobs/{job_id}/video")
async def get_job_video(job_id: str, download: int = 0) -> FileResponse:
    safe_id = _validate_job_id(job_id)
    video_path = TMP_ROOT / safe_id / "final.mp4"
    if not video_path.exists():
        raise HTTPException(status_code=404, detail="Video not found.")
    headers: dict[str, str] = {}
    if download == 1:
        headers["Content-Disposition"] = f'attachment; filename="{safe_id}.mp4"'
    return FileResponse(video_path, media_type="video/mp4", headers=headers)


def _validate_job_id(job_id: str) -> str:
    # Job IDs are UUID4 strings (see JobStore.create). Reject anything else
    # to prevent path traversal into /tmp/..
    try:
        return str(UUID(job_id))
    except (ValueError, AttributeError) as exc:
        raise HTTPException(status_code=404, detail="Job not found.") from exc


async def _resolve_source_text(
    *, file: UploadFile | None, url: str | None, query: str | None
) -> str:
    if file is not None:
        from app.ingest import extract_pdf_text

        file_bytes = await file.read()
        if len(file_bytes) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File too large. Max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
            )
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
            UUID(child.name)
        except ValueError:
            continue
        try:
            age_seconds = now - child.stat().st_mtime
            if age_seconds > STALE_TMP_AGE_SECONDS:
                shutil.rmtree(child, ignore_errors=True)
        except OSError:
            continue
