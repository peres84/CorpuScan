from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import UUID

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.investigation.chunker import chunk_document
from app.investigation.evidence_store import EvidenceReference
from app.investigation.models import ParsedDocument
from app.investigation.parsers import parse_document
from app.investigation.pipeline import (
    InvestigationJobState,
    InvestigationJobStep,
    InvestigationJobStore,
    run_investigation_pipeline,
)

logger = logging.getLogger(__name__)

router = APIRouter()
investigation_store = InvestigationJobStore()

MAX_UPLOAD_FILE_COUNT = 50
MAX_UPLOAD_BYTES = 50 * 1024 * 1024
SUPPORTED_EXTENSIONS = {".txt", ".pdf", ".xlsx", ".csv", ".docx", ".xml"}


# ── Response Models ──────────────────────────────────────────────────────────


class InvestigateResponse(BaseModel):
    job_id: str


class InvestigationStatusResponse(BaseModel):
    status: InvestigationJobState
    step: InvestigationJobStep
    progress: int = Field(ge=0, le=100)
    error: str | None = None


class FindingResponse(BaseModel):
    finding_id: str
    finding_text: str
    evidence: list[EvidenceReference]
    fraud_likelihood: float


class BufferRowResponse(BaseModel):
    doc_id: str
    filename: str
    notes_summary: str
    fraud_likelihood: float
    primary_next_doc: str | None
    alt_doc_leads: list[str]
    open_questions: list[str]


class ReportResponse(BaseModel):
    overall_fraud_likelihood: float
    documents_investigated: int
    total_documents: int
    findings: list[FindingResponse]
    buffer: list[BufferRowResponse]


# ── Endpoints ────────────────────────────────────────────────────────────────


@router.post("/investigate", response_model=InvestigateResponse)
async def create_investigation(
    files: list[UploadFile] = File(...),
    priority_doc_ids: str | None = Form(default=None),
) -> InvestigateResponse:
    """Accept multiple file uploads + optional priority doc IDs, return job_id."""
    if not files:
        raise HTTPException(status_code=400, detail="At least one file is required.")

    if len(files) > MAX_UPLOAD_FILE_COUNT:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {MAX_UPLOAD_FILE_COUNT} files allowed.",
        )

    # Validate files
    for upload in files:
        filename = upload.filename or ""
        ext = Path(filename).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format: {ext}. Supported: {', '.join(sorted(SUPPORTED_EXTENSIONS))}",
            )

    # Parse uploaded files
    documents: list[ParsedDocument] = []
    for upload in files:
        file_bytes = await upload.read()
        if len(file_bytes) > MAX_UPLOAD_BYTES:
            raise HTTPException(
                status_code=413,
                detail=f"File too large: {upload.filename}. Max {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
            )

        filename = upload.filename or "unknown"
        tmp_path = Path(TemporaryDirectory().name) / filename
        tmp_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_path.write_bytes(file_bytes)

        try:
            doc = parse_document(tmp_path)
            doc = chunk_document(doc)
            documents.append(doc)
        except Exception:
            logger.warning("Failed to parse uploaded file: %s", filename)
            continue

    if not documents:
        raise HTTPException(status_code=400, detail="No files could be parsed successfully.")

    # Parse priority doc IDs
    priority_ids: list[str] | None = None
    if priority_doc_ids:
        priority_ids = [p.strip() for p in priority_doc_ids.split(",") if p.strip()]

    job_id = investigation_store.create()
    asyncio.create_task(
        run_investigation_pipeline(
            job_store=investigation_store,
            job_id=job_id,
            documents=documents,
            priority_doc_ids=priority_ids,
        )
    )

    return InvestigateResponse(job_id=job_id)


@router.get("/investigations/{job_id}", response_model=InvestigationStatusResponse)
async def get_investigation_status(job_id: str) -> InvestigationStatusResponse:
    """Return status, progress, current step."""
    safe_id = _validate_job_id(job_id)
    job = investigation_store.get(safe_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Investigation not found.")

    return InvestigationStatusResponse(
        status=job.status,
        step=job.step,
        progress=job.progress,
        error=job.error,
    )


@router.get("/investigations/{job_id}/findings", response_model=list[FindingResponse])
async def get_investigation_findings(job_id: str) -> list[FindingResponse]:
    """Return findings list with evidence references."""
    safe_id = _validate_job_id(job_id)
    job = investigation_store.get(safe_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Investigation not found.")

    return [
        FindingResponse(
            finding_id=f.finding_id,
            finding_text=f.finding_text,
            evidence=f.evidence,
            fraud_likelihood=f.fraud_likelihood,
        )
        for f in job.findings
    ]


@router.get("/investigations/{job_id}/buffer", response_model=list[BufferRowResponse])
async def get_investigation_buffer(job_id: str) -> list[BufferRowResponse]:
    """Return investigation history (CSV-like buffer as JSON)."""
    safe_id = _validate_job_id(job_id)
    job = investigation_store.get(safe_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Investigation not found.")

    if job.investigation_state is None:
        return []

    return [
        BufferRowResponse(
            doc_id=row.doc_id,
            filename=row.filename,
            notes_summary=row.notes_summary,
            fraud_likelihood=row.fraud_likelihood,
            primary_next_doc=row.primary_next_doc,
            alt_doc_leads=row.alt_doc_leads,
            open_questions=row.open_questions,
        )
        for row in job.investigation_state.buffer
    ]


@router.get("/investigations/{job_id}/evidence/{finding_id}")
async def get_investigation_evidence(job_id: str, finding_id: str) -> FindingResponse:
    """Return specific evidence with document/page/passage."""
    safe_id = _validate_job_id(job_id)
    job = investigation_store.get(safe_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Investigation not found.")

    finding = job.evidence_store.get_finding(finding_id)
    if finding is None:
        raise HTTPException(status_code=404, detail="Finding not found.")

    return FindingResponse(
        finding_id=finding.finding_id,
        finding_text=finding.finding_text,
        evidence=finding.evidence,
        fraud_likelihood=finding.fraud_likelihood,
    )


@router.get("/investigations/{job_id}/report", response_model=ReportResponse)
async def get_investigation_report(job_id: str) -> ReportResponse:
    """Return final structured report (JSON)."""
    safe_id = _validate_job_id(job_id)
    job = investigation_store.get(safe_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Investigation not found.")

    if job.status != InvestigationJobState.DONE:
        raise HTTPException(status_code=400, detail="Investigation is not yet complete.")

    state = job.investigation_state
    findings_resp = [
        FindingResponse(
            finding_id=f.finding_id,
            finding_text=f.finding_text,
            evidence=f.evidence,
            fraud_likelihood=f.fraud_likelihood,
        )
        for f in job.findings
    ]

    buffer_resp = []
    if state:
        buffer_resp = [
            BufferRowResponse(
                doc_id=row.doc_id,
                filename=row.filename,
                notes_summary=row.notes_summary,
                fraud_likelihood=row.fraud_likelihood,
                primary_next_doc=row.primary_next_doc,
                alt_doc_leads=row.alt_doc_leads,
                open_questions=row.open_questions,
            )
            for row in state.buffer
        ]

    return ReportResponse(
        overall_fraud_likelihood=state.overall_fraud_likelihood if state else 0.0,
        documents_investigated=len(state.visited) if state else 0,
        total_documents=job.evidence_store.document_count,
        findings=findings_resp,
        buffer=buffer_resp,
    )


def _validate_job_id(job_id: str) -> str:
    """Validate that job_id is a valid UUID to prevent path traversal."""
    try:
        return str(UUID(job_id))
    except (ValueError, AttributeError) as exc:
        raise HTTPException(status_code=404, detail="Investigation not found.") from exc
