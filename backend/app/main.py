from __future__ import annotations

import asyncio
import logging
import logging.config
import shutil
import time
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import UUID

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
import yaml

from app.config import get_settings
from app.integrations.tavily import TavilyClient
from app.ingest import extract_pdf_documents
from app.jobs import JobStore
from app.logging_utils import stage_tag
from app.pipeline import run_pipeline
from app.render import ensure_ffmpeg_available
from app.schemas import (
    GenerateResponse,
    JobStatus,
    JobStep,
    OutputAspectRatio,
    PdfTemplateId,
    PipelineContext,
    SourceKind,
)

logger = logging.getLogger(__name__)

settings = get_settings()
job_store = JobStore()
REQUEST_TIMEOUT_SECONDS = 240
STALE_TMP_AGE_SECONDS = 30 * 60
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_UPLOAD_FILE_COUNT = 4
TMP_ROOT = Path("/tmp")
BACKEND_ROOT = Path(__file__).resolve().parent.parent
LOGGING_CONFIG_PATH = BACKEND_ROOT / "logging.yaml"
LOG_DIR = BACKEND_ROOT / "logs"


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_application_logging()
    logger.info("%s clearing all job temp state on startup", stage_tag("job"))
    cleanup_all_tmp_jobs()
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
    files: list[UploadFile] | None = File(default=None),
    file: UploadFile | None = File(default=None),
    url: str | None = Form(default=None),
    query: str | None = Form(default=None),
    template_id: PdfTemplateId | None = Form(default=None),
    output_aspect_ratio: OutputAspectRatio | None = Form(default=None),
) -> GenerateResponse:
    ensure_ffmpeg_available()
    pdf_uploads = _normalize_pdf_uploads(files=files, file=file)
    source_kind = _detect_source_kind(files=pdf_uploads, url=url, query=query)
    _validate_generate_request(
        files=pdf_uploads,
        url=url,
        query=query,
        template_id=template_id,
        output_aspect_ratio=output_aspect_ratio,
    )

    logger.info("generate request accepted (source=%s)", source_kind)
    source_text, pipeline_context = await _resolve_source_payload(
        files=pdf_uploads,
        url=url,
        query=query,
        template_id=template_id,
        output_aspect_ratio=output_aspect_ratio,
    )
    if not source_text.strip():
        raise HTTPException(status_code=400, detail="Could not extract text from the provided source.")

    job_id = job_store.create(source_kind=source_kind)
    job = job_store.get(job_id)
    if job is not None:
        job.pipeline_context = pipeline_context
    logger.info("[%s] source resolved from %s (%d chars)", job_id, source_kind, len(source_text))
    job_store.update_step(job_id, step=JobStep.INGEST, progress=10)
    asyncio.create_task(run_pipeline(job_store, job_id, source_text, pipeline_context))
    return GenerateResponse(job_id=job_id)


@app.get("/jobs/{job_id}", response_model=JobStatus)
async def get_job(job_id: str) -> JobStatus:
    safe_id = _validate_job_id(job_id)
    job = job_store.get(safe_id)
    if job is None:
        logger.warning("[%s] status requested but job was not found", safe_id)
        raise HTTPException(status_code=404, detail="Job not found.")
    return job.to_status()


@app.get("/jobs/{job_id}/video")
async def get_job_video(job_id: str, download: int = 0) -> FileResponse:
    safe_id = _validate_job_id(job_id)
    video_path = TMP_ROOT / safe_id / "final.mp4"
    if not video_path.exists():
        logger.warning("[%s] video requested but file was not found", safe_id)
        raise HTTPException(status_code=404, detail="Video not found.")
    logger.info("[%s] serving final video (download=%s)", safe_id, download)
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


def _detect_source_kind(
    *, files: list[UploadFile], url: str | None, query: str | None
) -> SourceKind:
    if files:
        return SourceKind.PDF
    if url:
        return SourceKind.URL
    if query:
        return SourceKind.QUERY
    return SourceKind.PDF


def configure_application_logging() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    if LOGGING_CONFIG_PATH.exists():
        with LOGGING_CONFIG_PATH.open("r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        logging.config.dictConfig(config)
    else:
        logging.basicConfig(level=logging.INFO, force=True)
    logger.info("%s application logging configured", stage_tag("request"))


async def _resolve_source_payload(
    *,
    files: list[UploadFile],
    url: str | None,
    query: str | None,
    template_id: PdfTemplateId | None,
    output_aspect_ratio: OutputAspectRatio | None,
) -> tuple[str, PipelineContext]:
    if files:
        uploads: list[tuple[str, bytes]] = []
        for upload in files:
            file_bytes = await upload.read()
            if len(file_bytes) > MAX_UPLOAD_BYTES:
                raise HTTPException(
                    status_code=413,
                    detail=f"File too large. Max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB per PDF.",
                )
            uploads.append((upload.filename or "report.pdf", file_bytes))
        try:
            documents, source_text, branding, company_name, period_label = extract_pdf_documents(uploads)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return source_text, PipelineContext(
            source_kind=SourceKind.PDF,
            output_aspect_ratio=output_aspect_ratio or OutputAspectRatio.DESKTOP,
            template_id=template_id,
            pdf_documents=documents,
            branding=branding,
            company_name=company_name,
            period_label=period_label,
        )

    tavily_client = TavilyClient(api_key=settings.tavily_api_key)
    if url:
        return await tavily_client.extract(url), PipelineContext(source_kind=SourceKind.URL)
    if query:
        results = await tavily_client.search(query)
        if not results:
            raise HTTPException(status_code=404, detail="No search results found for the provided query.")
        return await tavily_client.extract(results[0].url), PipelineContext(source_kind=SourceKind.QUERY)
    return "", PipelineContext(source_kind=SourceKind.PDF)


def _normalize_pdf_uploads(
    *, files: list[UploadFile] | None, file: UploadFile | None
) -> list[UploadFile]:
    uploads = list(files or [])
    if file is not None:
        uploads.append(file)
    return uploads


def _validate_generate_request(
    *,
    files: list[UploadFile],
    url: str | None,
    query: str | None,
    template_id: PdfTemplateId | None,
    output_aspect_ratio: OutputAspectRatio | None,
) -> None:
    provided_sources = sum(
        1 for present in [bool(files), bool(url and url.strip()), bool(query and query.strip())] if present
    )
    if provided_sources != 1:
        raise HTTPException(status_code=400, detail="Provide exactly one source: PDFs, url, or query.")

    if files:
        if len(files) > MAX_UPLOAD_FILE_COUNT:
            raise HTTPException(status_code=400, detail="Upload between 1 and 4 PDFs.")
        if template_id is None:
            raise HTTPException(status_code=400, detail="PDF mode requires a template_id.")
        if output_aspect_ratio is None:
            raise HTTPException(status_code=400, detail="PDF mode requires an output_aspect_ratio.")
        return

    if template_id is not None or output_aspect_ratio is not None:
        raise HTTPException(
            status_code=400,
            detail="template_id and output_aspect_ratio are supported for PDF mode only.",
        )


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


def cleanup_all_tmp_jobs() -> None:
    if not TMP_ROOT.exists():
        return
    for child in TMP_ROOT.iterdir():
        if not child.is_dir():
            continue
        try:
            UUID(child.name)
        except ValueError:
            continue
        shutil.rmtree(child, ignore_errors=True)
