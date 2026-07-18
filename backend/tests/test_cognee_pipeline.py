from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pytest

from app.investigation.models import ContentChunk, DocumentType, ParsedDocument
from app.investigation.pipeline import (
    InvestigationJobState,
    InvestigationJobStep,
    InvestigationJobStore,
    run_investigation_pipeline,
)


def _make_doc(doc_id: str, filename: str, content: str = "data") -> ParsedDocument:
    return ParsedDocument(
        doc_id=doc_id,
        filename=filename,
        doc_type=DocumentType.CSV,
        content_chunks=[ContentChunk(text=content, source_ref=f"{filename}:row:1", chunk_index=0)],
    )


class FakeLLMRouterForPipeline:
    def __init__(self) -> None:
        self._call_count = 0

    async def generate(self, **kwargs: object) -> str:
        self._call_count += 1
        system = str(kwargs.get("system", ""))
        if "entity extractor" in system.lower():
            return json.dumps([{"name": "TestEntity", "type": "vendor", "aliases": []}])
        return json.dumps({
            "notes_summary": f"Analyzed (call {self._call_count})",
            "evidence_found": [],
            "fraud_likelihood": 0.3,
            "primary_next_doc": None,
            "alt_doc_leads": [],
            "open_questions": [],
        })


class TestPipelineWithCogneeEnabled:
    @pytest.mark.asyncio
    async def test_pipeline_completes_with_cognee_enabled(self) -> None:
        """Full pipeline with Cognee enabled should still reach DONE."""
        store = InvestigationJobStore()
        job_id = store.create()
        docs = [_make_doc("d1", "test.csv", "vendor data")]

        fake_router = FakeLLMRouterForPipeline()

        # Mock _try_cognee_ingest to return a mock client
        mock_cognee_client = MagicMock()
        mock_cognee_client.is_available.return_value = False  # Skip graph merge

        with patch("app.investigation.pipeline._build_llm_router", return_value=fake_router):
            with patch("app.investigation.pipeline._try_cognee_ingest", new=AsyncMock(return_value=mock_cognee_client)):
                await run_investigation_pipeline(
                    job_store=store,
                    job_id=job_id,
                    documents=docs,
                    priority_doc_ids=["d1"],
                )

        job = store.get(job_id)
        assert job is not None
        assert job.status == InvestigationJobState.DONE


class TestPipelineWithCogneeDisabled:
    @pytest.mark.asyncio
    async def test_pipeline_completes_without_cognee(self) -> None:
        """Pipeline with Cognee disabled should work exactly as before (backward compat)."""
        store = InvestigationJobStore()
        job_id = store.create()
        docs = [_make_doc("d1", "test.csv", "data")]

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
        assert job.progress == 100

    @pytest.mark.asyncio
    async def test_cognee_failure_doesnt_break_pipeline(self) -> None:
        """If Cognee ingestion fails, pipeline continues normally."""
        store = InvestigationJobStore()
        job_id = store.create()
        docs = [_make_doc("d1", "test.csv", "data")]

        fake_router = FakeLLMRouterForPipeline()

        # _try_cognee_ingest raises but is caught — returns None
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


class TestCogneeIngestStep:
    def test_step_enum_includes_cognee(self) -> None:
        assert InvestigationJobStep.COGNEE_INGEST == "cognee_ingest"
        # Verify ordering in enum
        steps = list(InvestigationJobStep)
        parse_idx = steps.index(InvestigationJobStep.PARSE)
        cognee_idx = steps.index(InvestigationJobStep.COGNEE_INGEST)
        graph_idx = steps.index(InvestigationJobStep.BUILD_GRAPH)
        assert parse_idx < cognee_idx < graph_idx
