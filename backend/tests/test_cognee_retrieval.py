from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pytest

from app.cognee.client import CogneeClient
from app.cognee.retrieval import (
    _format_recall_results,
    _parse_related_entities,
    find_related_entities,
    register_cognee_mcp_tools,
    search_context,
)
from app.mcp.registry import _REGISTRY, get_tool


class TestSearchContext:
    @pytest.mark.asyncio
    async def test_returns_empty_when_unavailable(self) -> None:
        client = CogneeClient()
        result = await search_context(client, "test query")
        assert result == ""

    @pytest.mark.asyncio
    async def test_returns_context_when_available(self) -> None:
        client = CogneeClient()
        client._available = True

        mock_cognee = MagicMock()
        mock_cognee.recall = AsyncMock(return_value="Vendor 209101 created by MV-U05")
        mock_cognee.SearchType = MagicMock()
        mock_cognee.SearchType.GRAPH_COMPLETION = "GRAPH_COMPLETION"

        with patch.dict("sys.modules", {"cognee": mock_cognee}):
            result = await search_context(client, "vendor 209101")

        assert "209101" in result or "MV-U05" in result


class TestFindRelatedEntities:
    @pytest.mark.asyncio
    async def test_returns_empty_when_unavailable(self) -> None:
        client = CogneeClient()
        result = await find_related_entities(client, "VendorX")
        assert result == []

    @pytest.mark.asyncio
    async def test_parses_entity_results(self) -> None:
        client = CogneeClient()
        client._available = True

        mock_cognee = MagicMock()
        mock_cognee.recall = AsyncMock(return_value=[
            {"name": "MV-U05", "type": "person", "relationship": "created"},
            {"name": "209101", "type": "account", "relationship": "belongs_to"},
        ])
        mock_cognee.SearchType = MagicMock()
        mock_cognee.SearchType.GRAPH_COMPLETION = "GRAPH_COMPLETION"

        with patch.dict("sys.modules", {"cognee": mock_cognee}):
            result = await find_related_entities(client, "Ratio Consulting GmbH")

        assert len(result) == 2
        assert result[0]["name"] == "MV-U05"
        assert result[0]["relationship"] == "created"


class TestFormatRecallResults:
    def test_formats_string_result(self) -> None:
        result = _format_recall_results("Some context about vendors", "my query")
        assert "my query" in result
        assert "Some context about vendors" in result

    def test_formats_list_result(self) -> None:
        result = _format_recall_results(
            [{"content": "Entity A"}, {"text": "Entity B"}],
            "query",
        )
        assert "Entity A" in result
        assert "Entity B" in result

    def test_handles_empty(self) -> None:
        assert _format_recall_results(None, "q") == ""
        assert _format_recall_results([], "q") == ""


class TestParseRelatedEntities:
    def test_parses_list_of_dicts(self) -> None:
        data = [
            {"name": "VendorA", "type": "vendor", "relationship": "paid"},
            {"name": "PersonB", "type": "person"},
        ]
        result = _parse_related_entities(data)
        assert len(result) == 2
        assert result[0]["name"] == "VendorA"
        assert result[1]["relationship"] == "related"  # default

    def test_empty_input(self) -> None:
        assert _parse_related_entities(None) == []
        assert _parse_related_entities([]) == []


class TestCogneeMCPRegistration:
    def test_registers_three_tools(self) -> None:
        # Clear existing registrations
        _REGISTRY.pop("cognee.search", None)
        _REGISTRY.pop("cognee.related_entities", None)
        _REGISTRY.pop("cognee.relationship_graph", None)

        client = CogneeClient()
        register_cognee_mcp_tools(client)

        assert get_tool("cognee.search") is not None
        assert get_tool("cognee.related_entities") is not None
        assert get_tool("cognee.relationship_graph") is not None

        # Cleanup
        _REGISTRY.pop("cognee.search", None)
        _REGISTRY.pop("cognee.related_entities", None)
        _REGISTRY.pop("cognee.relationship_graph", None)


class TestAgentCogneeIntegration:
    @pytest.mark.asyncio
    async def test_agent_queries_cognee_during_investigation(self) -> None:
        """Verify the agent calls Cognee for context when available."""
        import json
        from app.investigation.agent import InvestigationAgent
        from app.investigation.evidence_store import EvidenceStore
        from app.investigation.graph import DocumentGraph
        from app.investigation.models import ContentChunk, DocumentType, ParsedDocument

        store = EvidenceStore()
        doc = ParsedDocument(
            doc_id="d1",
            filename="test.csv",
            doc_type=DocumentType.CSV,
            content_chunks=[ContentChunk(text="vendor data", source_ref="test.csv:row:1", chunk_index=0)],
        )
        store.add_document(doc)

        graph = DocumentGraph()
        graph.add_document("d1", "test.csv")

        # Mock LLM
        class FakeRouter:
            async def generate(self, **kwargs):
                return json.dumps({
                    "notes_summary": "checked doc",
                    "fraud_likelihood": 0.3,
                    "primary_next_doc": None,
                    "alt_doc_leads": [],
                    "open_questions": [],
                })

        # Mock Cognee client
        mock_cognee = MagicMock()
        mock_cognee.is_available.return_value = True

        agent = InvestigationAgent(
            llm_router=FakeRouter(),  # type: ignore[arg-type]
            evidence_store=store,
            graph=graph,
            cognee_client=mock_cognee,
            max_iterations=5,
        )

        # Patch cognee_search_context to verify it's called
        with patch("app.investigation.agent.cognee_search_context", new=AsyncMock(return_value="Cognee context: entity related")) as mock_search:
            await agent.investigate_document(doc)
            mock_search.assert_called_once()

    @pytest.mark.asyncio
    async def test_agent_works_without_cognee(self) -> None:
        """Verify agent works normally when cognee_client is None."""
        import json
        from app.investigation.agent import InvestigationAgent
        from app.investigation.evidence_store import EvidenceStore
        from app.investigation.graph import DocumentGraph
        from app.investigation.models import ContentChunk, DocumentType, ParsedDocument

        store = EvidenceStore()
        doc = ParsedDocument(
            doc_id="d1",
            filename="test.csv",
            doc_type=DocumentType.CSV,
            content_chunks=[ContentChunk(text="data", source_ref="test.csv:row:1", chunk_index=0)],
        )
        store.add_document(doc)

        graph = DocumentGraph()
        graph.add_document("d1", "test.csv")

        class FakeRouter:
            async def generate(self, **kwargs):
                return json.dumps({
                    "notes_summary": "analyzed",
                    "fraud_likelihood": 0.2,
                    "primary_next_doc": None,
                    "alt_doc_leads": [],
                    "open_questions": [],
                })

        agent = InvestigationAgent(
            llm_router=FakeRouter(),  # type: ignore[arg-type]
            evidence_store=store,
            graph=graph,
            cognee_client=None,
            max_iterations=5,
        )

        row = await agent.investigate_document(doc)
        assert row.filename == "test.csv"
        assert row.notes_summary == "analyzed"
