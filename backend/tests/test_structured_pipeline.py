from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.append(str(Path(__file__).resolve().parents[1]))

from app.investigation.agent import InvestigationAgent
from app.investigation.evidence_store import EvidenceStore
from app.investigation.graph import DocumentGraph
from app.investigation.models import ContentChunk, DocumentType, ParsedDocument
from app.investigation.pipeline import (
    InvestigationJobState,
    InvestigationJobStore,
    run_investigation_pipeline,
)
from app.investigation import structured
from app.investigation.structured import StructuredDataStore, StructuredFile


class PipelineRouter:
    async def generate(self, **kwargs: object) -> str:
        if "entity extractor" in str(kwargs.get("system", "")).lower():
            return "[]"
        return json.dumps(
            {
                "notes_summary": "No concerns found.",
                "evidence_found": [],
                "fraud_likelihood": 0.0,
                "primary_next_doc": None,
                "alt_doc_leads": [],
                "open_questions": [],
            }
        )


class CapturingRouter(PipelineRouter):
    def __init__(self) -> None:
        self.user_prompts: list[str] = []

    async def generate(self, **kwargs: object) -> str:
        user = kwargs.get("user")
        if isinstance(user, str):
            self.user_prompts.append(user)
        return await super().generate(**kwargs)


def _csv_document() -> ParsedDocument:
    return ParsedDocument(
        doc_id="ledger-1",
        filename="ledger.csv",
        doc_type=DocumentType.CSV,
        content_chunks=[
            ContentChunk(
                text="KREDITOR;BETRAG_EUR", source_ref="ledger.csv:row:1", chunk_index=0
            ),
            ContentChunk(
                text="209101;50000,00", source_ref="ledger.csv:row:2", chunk_index=1
            ),
        ],
        metadata={"delimiter": ";"},
    )


class TestStructuredPipelineIntegration:
    @pytest.mark.asyncio
    async def test_pipeline_writes_structured_data_json(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(structured, "STRUCTURED_DATA_ROOT", tmp_path)
        job_store = InvestigationJobStore()
        job_id = job_store.create()

        with patch(
            "app.investigation.pipeline._build_llm_router",
            return_value=PipelineRouter(),
        ):
            with patch(
                "app.investigation.pipeline._try_cognee_ingest",
                new=AsyncMock(return_value=None),
            ):
                await run_investigation_pipeline(job_store, job_id, [_csv_document()])

        job = job_store.get(job_id)
        assert job is not None
        assert job.status is InvestigationJobState.DONE
        assert job.structured_data_store.file_count == 1
        assert (tmp_path / job_id / "structured_data.json").exists()

    @pytest.mark.asyncio
    async def test_structured_data_is_included_in_agent_prompt(self) -> None:
        document = _csv_document()
        evidence_store = EvidenceStore()
        evidence_store.add_document(document)
        graph = DocumentGraph()
        graph.add_document(document.doc_id, document.filename)
        structured_store = StructuredDataStore()
        structured_store.add_file(
            StructuredFile(
                file_id=document.doc_id,
                filename=document.filename,
                extraction_method="deterministic",
                columns=["BETRAG_EUR"],
                normalized_columns=["amount"],
                rows=[{"BETRAG_EUR": "50000,00", "amount": "50000,00"}],
                row_count=1,
            )
        )
        router = CapturingRouter()
        agent = InvestigationAgent(
            llm_router=router,  # type: ignore[arg-type]
            evidence_store=evidence_store,
            graph=graph,
            structured_data_store=structured_store,
        )

        await agent.investigate_document(document)

        assert any(
            "## Structured Data Summary" in prompt for prompt in router.user_prompts
        )
        assert any("50000,00" in prompt for prompt in router.user_prompts)
        assert any('"row_number": "1"' in prompt for prompt in router.user_prompts)
        assert any("row:<number>" in prompt for prompt in router.user_prompts)
