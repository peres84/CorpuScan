from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app.investigation.buffer import InvestigationBufferRow, InvestigationState
from app.investigation.evidence_store import EvidenceReference, Finding
from app.investigation.models import ContentChunk, DocumentType, ParsedDocument
from app.investigation.pipeline import (
    InvestigationJobState,
    InvestigationJobStep,
)
from app.investigation.routes import investigation_store
from app.main import app

client = TestClient(app)


def _reset_store() -> None:
    """Clear the investigation store between tests."""
    investigation_store._jobs.clear()


def _create_done_job() -> str:
    """Helper to create a completed investigation job for query tests."""
    job_id = investigation_store.create()
    job = investigation_store.get(job_id)
    assert job is not None
    job.status = InvestigationJobState.DONE
    job.step = InvestigationJobStep.DONE
    job.progress = 100

    doc = ParsedDocument(
        doc_id="test_doc_1",
        filename="test.csv",
        doc_type=DocumentType.CSV,
        content_chunks=[ContentChunk(text="data", source_ref="test.csv:row:1", chunk_index=0)],
    )
    job.evidence_store.add_document(doc)

    finding = Finding(
        finding_id="f001",
        finding_text="Suspicious round amounts detected",
        evidence=[
            EvidenceReference(
                doc_id="test_doc_1",
                location="row:5",
                passage="€50,000 payment to unknown vendor",
                confidence=0.85,
            )
        ],
        fraud_likelihood=0.75,
    )
    job.evidence_store.add_finding(finding)
    job.findings = [finding]

    job.investigation_state = InvestigationState(
        buffer=[
            InvestigationBufferRow(
                doc_id="test_doc_1",
                filename="test.csv",
                notes_summary="Found suspicious activity",
                fraud_likelihood=0.75,
                primary_next_doc=None,
                alt_doc_leads=[],
                open_questions=["Is vendor real?"],
            )
        ],
        visited={"test_doc_1"},
        overall_fraud_likelihood=0.75,
        iteration_count=1,
    )

    return job_id


class TestPostInvestigate:
    def setup_method(self) -> None:
        _reset_store()

    def test_no_files_returns_400(self) -> None:
        response = client.post("/investigate")
        assert response.status_code == 422  # FastAPI validation error for missing files

    def test_unsupported_format_returns_400(self) -> None:
        response = client.post(
            "/investigate",
            files=[("files", ("image.png", b"fake png data", "image/png"))],
        )
        assert response.status_code == 400
        assert "Unsupported file format" in response.json()["detail"]

    def test_valid_csv_upload_returns_job_id(self) -> None:
        csv_content = b"DATUM;BETRAG;VENDOR\n01.01.2025;50000;TestCorp\n"
        response = client.post(
            "/investigate",
            files=[("files", ("data.csv", csv_content, "text/csv"))],
        )
        assert response.status_code == 200
        data = response.json()
        assert "job_id" in data
        assert len(data["job_id"]) > 0


class TestGetInvestigationStatus:
    def setup_method(self) -> None:
        _reset_store()

    def test_missing_job_returns_404(self) -> None:
        response = client.get("/investigations/00000000-0000-0000-0000-000000000000")
        assert response.status_code == 404

    def test_invalid_id_returns_404(self) -> None:
        response = client.get("/investigations/not-a-uuid")
        assert response.status_code == 404

    def test_existing_job_returns_status(self) -> None:
        job_id = _create_done_job()
        response = client.get(f"/investigations/{job_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "done"
        assert data["step"] == "done"
        assert data["progress"] == 100


class TestGetFindings:
    def setup_method(self) -> None:
        _reset_store()

    def test_returns_findings(self) -> None:
        job_id = _create_done_job()
        response = client.get(f"/investigations/{job_id}/findings")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["finding_id"] == "f001"
        assert data[0]["fraud_likelihood"] == 0.75
        assert len(data[0]["evidence"]) == 1

    def test_missing_job_returns_404(self) -> None:
        response = client.get("/investigations/00000000-0000-0000-0000-000000000000/findings")
        assert response.status_code == 404


class TestGetBuffer:
    def setup_method(self) -> None:
        _reset_store()

    def test_returns_buffer(self) -> None:
        job_id = _create_done_job()
        response = client.get(f"/investigations/{job_id}/buffer")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["filename"] == "test.csv"
        assert data[0]["fraud_likelihood"] == 0.75
        assert "Is vendor real?" in data[0]["open_questions"]


class TestGetEvidence:
    def setup_method(self) -> None:
        _reset_store()

    def test_returns_evidence(self) -> None:
        job_id = _create_done_job()
        response = client.get(f"/investigations/{job_id}/evidence/f001")
        assert response.status_code == 200
        data = response.json()
        assert data["finding_id"] == "f001"
        assert len(data["evidence"]) == 1
        assert data["evidence"][0]["passage"] == "€50,000 payment to unknown vendor"

    def test_missing_finding_returns_404(self) -> None:
        job_id = _create_done_job()
        response = client.get(f"/investigations/{job_id}/evidence/nonexistent")
        assert response.status_code == 404


class TestGetReport:
    def setup_method(self) -> None:
        _reset_store()

    def test_returns_report_when_done(self) -> None:
        job_id = _create_done_job()
        response = client.get(f"/investigations/{job_id}/report")
        assert response.status_code == 200
        data = response.json()
        assert data["overall_fraud_likelihood"] == 0.75
        assert data["documents_investigated"] == 1
        assert data["total_documents"] == 1
        assert len(data["findings"]) == 1
        assert len(data["buffer"]) == 1

    def test_not_done_returns_400(self) -> None:
        job_id = investigation_store.create()
        response = client.get(f"/investigations/{job_id}/report")
        assert response.status_code == 400
        assert "not yet complete" in response.json()["detail"]
