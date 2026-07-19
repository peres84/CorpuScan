from __future__ import annotations

import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from app.investigation.buffer import InvestigationBufferRow, InvestigationState
from app.investigation.evidence_store import Entity
from app.investigation.models import ContentChunk, DocumentType, ParsedDocument
from app.investigation.pipeline import InvestigationJobState, InvestigationJobStep
from app.investigation.routes import investigation_store
from app.main import app

client = TestClient(app)


def _reset_store() -> None:
    investigation_store._jobs.clear()


def _create_job_with_graph() -> str:
    """Create a completed job with entities and graph edges for testing."""
    job_id = investigation_store.create()
    job = investigation_store.get(job_id)
    assert job is not None
    job.status = InvestigationJobState.DONE
    job.step = InvestigationJobStep.DONE
    job.progress = 100

    doc1 = ParsedDocument(
        doc_id="doc1", filename="ledger.csv", doc_type=DocumentType.CSV,
        content_chunks=[ContentChunk(text="data", source_ref="ledger.csv:row:1", chunk_index=0)],
    )
    doc2 = ParsedDocument(
        doc_id="doc2", filename="vendors.csv", doc_type=DocumentType.CSV,
        content_chunks=[ContentChunk(text="data", source_ref="vendors.csv:row:1", chunk_index=0)],
    )
    job.evidence_store.add_document(doc1)
    job.evidence_store.add_document(doc2)

    job.graph.add_document("doc1", "ledger.csv")
    job.graph.add_document("doc2", "vendors.csv")

    entity1 = Entity(name="Ratio Consulting GmbH", entity_type="vendor", source_doc_id="doc1")
    entity2 = Entity(name="Ratio Consulting GmbH", entity_type="vendor", source_doc_id="doc2")
    entity3 = Entity(name="MV-U05", entity_type="person", source_doc_id="doc2")

    job.evidence_store.add_entity(entity1)
    job.evidence_store.add_entity(Entity(name="MV-U05", entity_type="person", source_doc_id="doc2"))
    job.graph.add_entity_to_document("doc1", entity1)
    job.graph.add_entity_to_document("doc2", entity2)
    job.graph.add_entity_to_document("doc2", entity3)

    job.investigation_state = InvestigationState(
        buffer=[InvestigationBufferRow(doc_id="doc1", filename="ledger.csv", fraud_likelihood=0.8)],
        visited={"doc1", "doc2"},
        overall_fraud_likelihood=0.8,
        iteration_count=2,
    )

    return job_id


class TestGetGraph:
    def setup_method(self) -> None:
        _reset_store()

    def test_returns_graph(self) -> None:
        job_id = _create_job_with_graph()
        response = client.get(f"/investigations/{job_id}/graph")
        assert response.status_code == 200
        data = response.json()
        assert "entities" in data
        assert "relationships" in data
        assert len(data["entities"]) >= 1

    def test_missing_job_returns_404(self) -> None:
        response = client.get("/investigations/00000000-0000-0000-0000-000000000000/graph")
        assert response.status_code == 404


class TestGetRelated:
    def setup_method(self) -> None:
        _reset_store()

    def test_returns_related_entities(self) -> None:
        job_id = _create_job_with_graph()
        response = client.get(f"/investigations/{job_id}/related?entity=Ratio Consulting GmbH")
        assert response.status_code == 200
        data = response.json()
        # MV-U05 is in the same doc as Ratio Consulting GmbH
        names = [item["name"] for item in data]
        assert "MV-U05" in names

    def test_empty_entity_returns_400(self) -> None:
        job_id = _create_job_with_graph()
        response = client.get(f"/investigations/{job_id}/related?entity=")
        assert response.status_code == 400

    def test_missing_job_returns_404(self) -> None:
        response = client.get("/investigations/00000000-0000-0000-0000-000000000000/related?entity=test")
        assert response.status_code == 404


class TestBuildMemory:
    def setup_method(self) -> None:
        _reset_store()

    def test_cognee_disabled_returns_503(self) -> None:
        from unittest.mock import patch, MagicMock
        job_id = _create_job_with_graph()
        mock_settings = MagicMock()
        mock_settings.cognee_enabled = False
        with patch("app.config.get_settings", return_value=mock_settings):
            response = client.post(f"/investigations/{job_id}/memory/build")
        assert response.status_code == 503

    def test_missing_job_returns_404(self) -> None:
        response = client.post("/investigations/00000000-0000-0000-0000-000000000000/memory/build")
        assert response.status_code == 404
