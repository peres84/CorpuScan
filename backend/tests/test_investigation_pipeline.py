from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pytest

from app.investigation.models import ContentChunk, DocumentType, ParsedDocument
from app.investigation.pipeline import (
    InvestigationJobState,
    InvestigationJobStep,
    InvestigationJobStore,
    run_investigation_pipeline,
)


def _make_doc(doc_id: str, filename: str, content: str = "test content") -> ParsedDocument:
    return ParsedDocument(
        doc_id=doc_id,
        filename=filename,
        doc_type=DocumentType.CSV,
        content_chunks=[ContentChunk(text=content, source_ref=f"{filename}:row:1", chunk_index=0)],
    )


class FakeLLMRouterForPipeline:
    """Returns entity extraction responses and investigation responses."""

    def __init__(self) -> None:
        self._call_count = 0

    async def generate(self, **kwargs: object) -> str:
        self._call_count += 1
        system = str(kwargs.get("system", ""))

        # Entity extraction calls
        if "entity extractor" in system.lower():
            return json.dumps([
                {"name": "TestVendor", "type": "vendor", "aliases": []},
            ])

        # Investigation agent calls
        return json.dumps({
            "notes_summary": f"Analyzed document (call {self._call_count})",
            "evidence_found": [],
            "fraud_likelihood": 0.3,
            "primary_next_doc": None,
            "alt_doc_leads": [],
            "open_questions": [],
            "hypothesis": None,
        })


class TestInvestigationJobStore:
    def test_create_and_get(self) -> None:
        store = InvestigationJobStore()
        job_id = store.create()
        job = store.get(job_id)
        assert job is not None
        assert job.status == InvestigationJobState.PENDING
        assert job.step == InvestigationJobStep.PARSE

    def test_update_step(self) -> None:
        store = InvestigationJobStore()
        job_id = store.create()
        store.update_step(job_id, step=InvestigationJobStep.BUILD_GRAPH, progress=30)
        job = store.get(job_id)
        assert job is not None
        assert job.step == InvestigationJobStep.BUILD_GRAPH
        assert job.progress == 30
        assert job.status == InvestigationJobState.RUNNING

    def test_set_error(self) -> None:
        store = InvestigationJobStore()
        job_id = store.create()
        store.set_error(job_id, "Something broke")
        job = store.get(job_id)
        assert job is not None
        assert job.status == InvestigationJobState.ERROR
        assert job.error == "Something broke"

    def test_set_done(self) -> None:
        store = InvestigationJobStore()
        job_id = store.create()
        store.set_done(job_id)
        job = store.get(job_id)
        assert job is not None
        assert job.status == InvestigationJobState.DONE
        assert job.progress == 100

    def test_get_missing_returns_none(self) -> None:
        store = InvestigationJobStore()
        assert store.get("nonexistent") is None


class TestRunInvestigationPipeline:
    @pytest.mark.asyncio
    async def test_full_pipeline_reaches_done(self) -> None:
        """Integration test: full pipeline with mocked LLM reaches DONE state."""
        store = InvestigationJobStore()
        job_id = store.create()

        docs = [
            _make_doc("d1", "ledger.csv", "200007;Castor Papier GmbH;9780,00"),
            _make_doc("d2", "vendors.csv", "209101;Ratio Consulting GmbH"),
            _make_doc("d3", "receipts.csv", "WE001;200007;Material"),
        ]

        fake_router = FakeLLMRouterForPipeline()

        with patch("app.investigation.pipeline._build_llm_router", return_value=fake_router):
            with patch("app.investigation.pipeline._try_cognee_ingest", new=AsyncMock(return_value=None)):
                await run_investigation_pipeline(
                    job_store=store,
                    job_id=job_id,
                    documents=docs,
                    priority_doc_ids=["d1"],
                )

        job = store.get(job_id)
        assert job is not None
        assert job.status == InvestigationJobState.DONE
        assert job.step == InvestigationJobStep.DONE
        assert job.progress == 100
        assert job.investigation_state is not None
        assert len(job.investigation_state.visited) > 0

    @pytest.mark.asyncio
    async def test_pipeline_error_handling(self) -> None:
        """Verify pipeline stores error on failure."""
        store = InvestigationJobStore()
        job_id = store.create()

        with patch("app.investigation.pipeline._build_llm_router", side_effect=RuntimeError("No LLM")):
            with patch("app.investigation.pipeline._try_cognee_ingest", new=AsyncMock(return_value=None)):
                await run_investigation_pipeline(
                    job_store=store,
                    job_id=job_id,
                    documents=[],
                )

        job = store.get(job_id)
        assert job is not None
        assert job.status == InvestigationJobState.ERROR
        assert "No LLM" in (job.error or "")

    @pytest.mark.asyncio
    async def test_pipeline_with_priority_docs(self) -> None:
        """Verify priority docs are passed as start nodes."""
        store = InvestigationJobStore()
        job_id = store.create()

        docs = [
            _make_doc("d1", "a.csv", "data a"),
            _make_doc("d2", "b.csv", "data b"),
            _make_doc("d3", "c.csv", "data c"),
        ]

        fake_router = FakeLLMRouterForPipeline()

        with patch("app.investigation.pipeline._build_llm_router", return_value=fake_router):
            with patch("app.investigation.pipeline._try_cognee_ingest", new=AsyncMock(return_value=None)):
                await run_investigation_pipeline(
                    job_store=store,
                    job_id=job_id,
                    documents=docs,
                    priority_doc_ids=["d2"],
                )

        job = store.get(job_id)
        assert job is not None
        assert job.status == InvestigationJobState.DONE
        assert job.investigation_state is not None
        assert "d2" in job.investigation_state.visited
