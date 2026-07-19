from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pytest

from app.cognee.schemas import CogneeEntity, CogneeGraphResponse, CogneeRelationship
from app.investigation.buffer import InvestigationBufferRow, InvestigationState
from app.investigation.evidence_store import EvidenceStore
from app.investigation.report import (
    InvestigationReport,
    ReportGenerator,
    build_knowledge_graph_summary,
    build_relationship_chains,
)


def _build_state() -> InvestigationState:
    return InvestigationState(
        buffer=[
            InvestigationBufferRow(
                doc_id="d1", filename="test.csv",
                notes_summary="Found suspicious activity",
                fraud_likelihood=0.8,
            ),
        ],
        visited={"d1"},
        overall_fraud_likelihood=0.8,
        iteration_count=1,
    )


def _build_cognee_graph() -> CogneeGraphResponse:
    return CogneeGraphResponse(
        entities=[
            CogneeEntity(name="MV-U05", entity_type="person"),
            CogneeEntity(name="Ratio Consulting GmbH", entity_type="vendor"),
            CogneeEntity(name="209101", entity_type="account"),
            CogneeEntity(name="€248,000", entity_type="amount"),
        ],
        relationships=[
            CogneeRelationship(source_entity="MV-U05", target_entity="Ratio Consulting GmbH", relationship_type="created"),
            CogneeRelationship(source_entity="Ratio Consulting GmbH", target_entity="209101", relationship_type="has_account"),
            CogneeRelationship(source_entity="Ratio Consulting GmbH", target_entity="€248,000", relationship_type="invoiced"),
        ],
    )


class TestBuildRelationshipChains:
    def test_builds_chains_from_cognee_graph(self) -> None:
        graph = _build_cognee_graph()
        chains = build_relationship_chains(graph)
        assert len(chains) >= 1
        # Should contain MV-U05 → created → Ratio Consulting GmbH chain
        assert any("MV-U05" in chain and "created" in chain for chain in chains)

    def test_empty_graph_returns_empty(self) -> None:
        graph = CogneeGraphResponse()
        chains = build_relationship_chains(graph)
        assert chains == []

    def test_non_cognee_input_returns_empty(self) -> None:
        chains = build_relationship_chains(None)
        assert chains == []


class TestBuildKnowledgeGraphSummary:
    def test_builds_summary(self) -> None:
        graph = _build_cognee_graph()
        summary = build_knowledge_graph_summary(graph)
        assert "4 entities" in summary
        assert "3 relationships" in summary
        assert "person" in summary
        assert "vendor" in summary

    def test_empty_graph_returns_empty_string(self) -> None:
        graph = CogneeGraphResponse()
        summary = build_knowledge_graph_summary(graph)
        assert summary == ""


class TestReportWithCognee:
    @pytest.mark.asyncio
    async def test_report_includes_chains_when_cognee_available(self) -> None:
        """Verify report includes relationship chains from Cognee."""

        class FakeLLM:
            async def generate(self, **kwargs) -> str:
                return json.dumps({
                    "executive_summary": "Investigation found issues.",
                    "findings": [],
                    "timeline": [],
                    "entity_relationships": [],
                    "fraud_assessment": {"overall_likelihood": 0.8, "estimated_financial_impact": "Unknown", "schemes_identified": []},
                    "remaining_questions": [],
                })

        state = _build_state()
        store = EvidenceStore()
        cognee_graph = _build_cognee_graph()

        generator = ReportGenerator(llm_router=FakeLLM())  # type: ignore[arg-type]
        report = await generator.generate(state, store, cognee_graph=cognee_graph)

        assert isinstance(report, InvestigationReport)
        assert len(report.relationship_chains) >= 1
        assert report.knowledge_graph_summary != ""
        assert "entities" in report.knowledge_graph_summary

    @pytest.mark.asyncio
    async def test_report_generates_without_cognee(self) -> None:
        """Verify report still works when cognee_graph is None."""

        class FakeLLM:
            async def generate(self, **kwargs) -> str:
                return json.dumps({
                    "executive_summary": "Basic report.",
                    "findings": [],
                    "timeline": [],
                    "entity_relationships": [],
                    "fraud_assessment": {"overall_likelihood": 0.5, "estimated_financial_impact": "Unknown", "schemes_identified": []},
                    "remaining_questions": [],
                })

        state = _build_state()
        store = EvidenceStore()

        generator = ReportGenerator(llm_router=FakeLLM())  # type: ignore[arg-type]
        report = await generator.generate(state, store, cognee_graph=None)

        assert isinstance(report, InvestigationReport)
        assert report.relationship_chains == []
        assert report.knowledge_graph_summary == ""
