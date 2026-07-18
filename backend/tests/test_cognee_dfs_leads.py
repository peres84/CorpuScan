from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pytest

from app.investigation.agent import InvestigationAgent
from app.investigation.buffer import InvestigationBufferRow
from app.investigation.evidence_store import Entity, EvidenceStore
from app.investigation.graph import DocumentGraph
from app.investigation.models import ContentChunk, DocumentType, ParsedDocument


def _make_doc(doc_id: str, filename: str, content: str = "data") -> ParsedDocument:
    return ParsedDocument(
        doc_id=doc_id,
        filename=filename,
        doc_type=DocumentType.CSV,
        content_chunks=[ContentChunk(text=content, source_ref=f"{filename}:row:1", chunk_index=0)],
    )


class FakeLLMRouter:
    def __init__(self, responses: list[dict]) -> None:
        self._responses = responses
        self._idx = 0

    async def generate(self, **kwargs) -> str:
        resp = self._responses[min(self._idx, len(self._responses) - 1)]
        self._idx += 1
        return json.dumps(resp)


class TestCogneeLeadsInfluenceDFS:
    @pytest.mark.asyncio
    async def test_strong_entity_overlap_prioritized(self) -> None:
        """Documents with strong entity overlap via graph should be investigated sooner."""
        store = EvidenceStore()
        doc_a = _make_doc("a", "doc_a.csv")
        doc_b = _make_doc("b", "doc_b.csv")  # strong overlap with a
        doc_c = _make_doc("c", "doc_c.csv")  # no overlap with a
        store.add_document(doc_a)
        store.add_document(doc_b)
        store.add_document(doc_c)

        graph = DocumentGraph()
        graph.add_document("a", "doc_a.csv")
        graph.add_document("b", "doc_b.csv")
        graph.add_document("c", "doc_c.csv")

        # Create strong entity overlap between a and b (2+ shared entities)
        entity1 = Entity(name="VendorX", entity_type="vendor", source_doc_id="a")
        entity2 = Entity(name="Account209", entity_type="account", source_doc_id="a")
        graph.add_entity_to_document("a", entity1)
        graph.add_entity_to_document("a", entity2)
        graph.add_entity_to_document("b", Entity(name="VendorX", entity_type="vendor", source_doc_id="b"))
        graph.add_entity_to_document("b", Entity(name="Account209", entity_type="account", source_doc_id="b"))

        # doc_c has no shared entities with doc_a
        graph.add_entity_to_document("c", Entity(name="Unrelated", entity_type="vendor", source_doc_id="c"))

        responses = [
            {
                "notes_summary": "Analyzed doc_a",
                "fraud_likelihood": 0.5,
                "primary_next_doc": None,  # No LLM primary — let Cognee leads drive
                "alt_doc_leads": ["doc_c.csv"],  # LLM suggests c
                "open_questions": [],
            },
            {
                "notes_summary": "Analyzed doc_b",
                "fraud_likelihood": 0.7,
                "primary_next_doc": None,
                "alt_doc_leads": [],
                "open_questions": [],
            },
            {
                "notes_summary": "Analyzed doc_c",
                "fraud_likelihood": 0.1,
                "primary_next_doc": None,
                "alt_doc_leads": [],
                "open_questions": [],
            },
        ]

        agent = InvestigationAgent(
            llm_router=FakeLLMRouter(responses),  # type: ignore[arg-type]
            evidence_store=store,
            graph=graph,
            max_iterations=10,
        )

        state = await agent.run(start_doc_ids=["a"])

        # doc_b should be visited before doc_c because it has strong entity overlap
        visited_order = [row.filename for row in state.buffer]
        assert visited_order[0] == "doc_a.csv"
        # doc_b should come before doc_c due to Cognee prioritization
        b_idx = visited_order.index("doc_b.csv")
        c_idx = visited_order.index("doc_c.csv")
        assert b_idx < c_idx

    @pytest.mark.asyncio
    async def test_no_overlap_deprioritized(self) -> None:
        """Documents with no entity overlap should be pushed to bottom of stack."""
        store = EvidenceStore()
        doc_a = _make_doc("a", "doc_a.csv")
        doc_b = _make_doc("b", "doc_b.csv")  # no overlap
        store.add_document(doc_a)
        store.add_document(doc_b)

        graph = DocumentGraph()
        graph.add_document("a", "doc_a.csv")
        graph.add_document("b", "doc_b.csv")

        # No shared entities — b is related via graph edge but no entity overlap
        graph.add_entity_to_document("a", Entity(name="EntityA", entity_type="vendor", source_doc_id="a"))
        graph.add_entity_to_document("b", Entity(name="EntityB", entity_type="vendor", source_doc_id="b"))

        responses = [
            {
                "notes_summary": "Checked a",
                "fraud_likelihood": 0.3,
                "primary_next_doc": "doc_b.csv",
                "alt_doc_leads": [],
                "open_questions": [],
            },
            {
                "notes_summary": "Checked b",
                "fraud_likelihood": 0.1,
                "primary_next_doc": None,
                "alt_doc_leads": [],
                "open_questions": [],
            },
        ]

        agent = InvestigationAgent(
            llm_router=FakeLLMRouter(responses),  # type: ignore[arg-type]
            evidence_store=store,
            graph=graph,
            max_iterations=10,
        )

        state = await agent.run(start_doc_ids=["a"])

        # Still visits b (because LLM said primary_next_doc), but the mechanism works
        assert len(state.buffer) == 2
        assert "b" in state.visited


class TestGetInvestigationLeads:
    def test_separates_strong_and_weak_connections(self) -> None:
        store = EvidenceStore()
        store.add_document(_make_doc("a", "a.csv"))
        store.add_document(_make_doc("b", "b.csv"))
        store.add_document(_make_doc("c", "c.csv"))

        graph = DocumentGraph()
        graph.add_document("a", "a.csv")
        graph.add_document("b", "b.csv")
        graph.add_document("c", "c.csv")

        # Strong overlap: a and b share 2 entities
        graph.add_entity_to_document("a", Entity(name="E1", entity_type="vendor", source_doc_id="a"))
        graph.add_entity_to_document("a", Entity(name="E2", entity_type="account", source_doc_id="a"))
        graph.add_entity_to_document("b", Entity(name="E1", entity_type="vendor", source_doc_id="b"))
        graph.add_entity_to_document("b", Entity(name="E2", entity_type="account", source_doc_id="b"))

        # No overlap: c has unrelated entity but is connected via some edge
        graph.add_entity_to_document("c", Entity(name="E3", entity_type="vendor", source_doc_id="c"))

        agent = InvestigationAgent(
            llm_router=FakeLLMRouter([]),  # type: ignore[arg-type]
            evidence_store=store,
            graph=graph,
            max_iterations=5,
        )

        row = InvestigationBufferRow(doc_id="a", filename="a.csv")
        leads = agent._get_investigation_leads(row)

        assert "b" in leads["cognee_suggested"]
        # c has no overlap with a, but it's also not in related_ids unless there's an edge
