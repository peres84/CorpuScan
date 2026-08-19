from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pytest

from app.investigation.agent import InvestigationAgent
from app.investigation.buffer import InvestigationBufferRow, InvestigationState
from app.investigation.evidence_store import EvidenceStore
from app.investigation.graph import DocumentGraph
from app.investigation.models import ContentChunk, DocumentType, ParsedDocument


def _make_doc(
    doc_id: str, filename: str, content: str = "test content"
) -> ParsedDocument:
    return ParsedDocument(
        doc_id=doc_id,
        filename=filename,
        doc_type=DocumentType.CSV,
        content_chunks=[
            ContentChunk(text=content, source_ref=f"{filename}:row:1", chunk_index=0)
        ],
    )


class FakeLLMRouter:
    """Mock LLM router that returns pre-configured responses based on call order."""

    def __init__(self, responses: list[dict[str, object]]) -> None:
        self._responses = responses
        self._call_count = 0
        self.calls: list[dict[str, object]] = []

    async def generate(self, **kwargs: object) -> str:
        self.calls.append(kwargs)
        idx = min(self._call_count, len(self._responses) - 1)
        self._call_count += 1
        return json.dumps(self._responses[idx])


class TestInvestigationAgentDFS:
    @pytest.mark.asyncio
    async def test_dfs_traversal_order(self) -> None:
        """Verify agent follows DFS order: visits primary_next_doc before alt leads."""
        store = EvidenceStore()
        doc_a = _make_doc("a", "doc_a.csv", "Starting document")
        doc_b = _make_doc("b", "doc_b.csv", "Second document")
        doc_c = _make_doc("c", "doc_c.csv", "Third document")
        store.add_document(doc_a)
        store.add_document(doc_b)
        store.add_document(doc_c)

        graph = DocumentGraph()
        graph.add_document("a", "doc_a.csv")
        graph.add_document("b", "doc_b.csv")
        graph.add_document("c", "doc_c.csv")

        # LLM responses guide the DFS:
        # doc_a -> primary: doc_b, alt: doc_c
        # doc_b -> no leads (dead end)
        # doc_c -> no leads (dead end)
        responses = [
            {
                "notes_summary": "Found suspicious activity in doc_a",
                "evidence_found": [],
                "fraud_likelihood": 0.5,
                "primary_next_doc": "doc_b.csv",
                "alt_doc_leads": ["doc_c.csv"],
                "open_questions": ["Is vendor real?"],
                "hypothesis": "Possible fake vendor",
            },
            {
                "notes_summary": "doc_b confirms suspicion",
                "evidence_found": [],
                "fraud_likelihood": 0.7,
                "primary_next_doc": None,
                "alt_doc_leads": [],
                "open_questions": [],
                "hypothesis": "Fake vendor confirmed",
            },
            {
                "notes_summary": "doc_c is clean",
                "evidence_found": [],
                "fraud_likelihood": 0.1,
                "primary_next_doc": None,
                "alt_doc_leads": [],
                "open_questions": [],
                "hypothesis": None,
            },
        ]

        router = FakeLLMRouter(responses)
        agent = InvestigationAgent(
            llm_router=router,  # type: ignore[arg-type]
            evidence_store=store,
            graph=graph,
            max_iterations=10,
        )

        state = await agent.run(start_doc_ids=["a"])

        # Should visit in DFS order: a -> b (primary) -> c (alt)
        visited_filenames = [row.filename for row in state.buffer]
        assert visited_filenames == ["doc_a.csv", "doc_b.csv", "doc_c.csv"]

        # Overall likelihood should be the max (0.7 from doc_b)
        assert state.overall_fraud_likelihood == pytest.approx(0.7)

    @pytest.mark.asyncio
    async def test_terminates_when_graph_fully_explored(self) -> None:
        """Verify investigation terminates when all documents are visited."""
        store = EvidenceStore()
        doc_a = _make_doc("a", "doc_a.csv")
        doc_b = _make_doc("b", "doc_b.csv")
        store.add_document(doc_a)
        store.add_document(doc_b)

        graph = DocumentGraph()
        graph.add_document("a", "doc_a.csv")
        graph.add_document("b", "doc_b.csv")

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
                "fraud_likelihood": 0.2,
                "primary_next_doc": None,
                "alt_doc_leads": [],
                "open_questions": [],
            },
        ]

        router = FakeLLMRouter(responses)
        agent = InvestigationAgent(
            llm_router=router,  # type: ignore[arg-type]
            evidence_store=store,
            graph=graph,
            max_iterations=50,
        )

        state = await agent.run(start_doc_ids=["a"])

        assert state.is_terminated() or len(state.stack) == 0
        assert len(state.visited) == 2
        assert state.iteration_count == 2

    @pytest.mark.asyncio
    async def test_max_iterations_terminates(self) -> None:
        """Verify investigation stops at max_iterations."""
        store = EvidenceStore()
        # Create a chain of documents where each leads to the next
        for i in range(20):
            store.add_document(_make_doc(str(i), f"doc_{i}.csv"))

        graph = DocumentGraph()
        for i in range(20):
            graph.add_document(str(i), f"doc_{i}.csv")

        # Each document points to the next
        responses = [
            {
                "notes_summary": f"Checked doc_{i}",
                "fraud_likelihood": 0.1,
                "primary_next_doc": f"doc_{i + 1}.csv" if i < 19 else None,
                "alt_doc_leads": [],
                "open_questions": [],
            }
            for i in range(20)
        ]

        router = FakeLLMRouter(responses)
        agent = InvestigationAgent(
            llm_router=router,  # type: ignore[arg-type]
            evidence_store=store,
            graph=graph,
            max_iterations=5,
        )

        state = await agent.run(start_doc_ids=["0"])

        assert state.iteration_count == 5
        assert state.is_terminated()

    @pytest.mark.asyncio
    async def test_skips_already_visited(self) -> None:
        """Verify agent doesn't revisit documents."""
        store = EvidenceStore()
        doc_a = _make_doc("a", "doc_a.csv")
        doc_b = _make_doc("b", "doc_b.csv")
        store.add_document(doc_a)
        store.add_document(doc_b)

        graph = DocumentGraph()
        graph.add_document("a", "doc_a.csv")
        graph.add_document("b", "doc_b.csv")

        # doc_a leads to doc_b, doc_b leads back to doc_a (cycle)
        responses = [
            {
                "notes_summary": "Checked a",
                "fraud_likelihood": 0.4,
                "primary_next_doc": "doc_b.csv",
                "alt_doc_leads": [],
                "open_questions": [],
            },
            {
                "notes_summary": "Checked b",
                "fraud_likelihood": 0.3,
                "primary_next_doc": "doc_a.csv",  # cycle back!
                "alt_doc_leads": [],
                "open_questions": [],
            },
        ]

        router = FakeLLMRouter(responses)
        agent = InvestigationAgent(
            llm_router=router,  # type: ignore[arg-type]
            evidence_store=store,
            graph=graph,
            max_iterations=10,
        )

        state = await agent.run(start_doc_ids=["a"])

        # Should only visit each doc once
        assert len(state.buffer) == 2
        assert state.iteration_count == 2


class TestInvestigationState:
    def test_format_buffer_empty(self) -> None:
        state = InvestigationState()
        assert state.format_buffer_for_llm() == "No previous investigation steps."

    def test_format_buffer_with_rows(self) -> None:
        state = InvestigationState()
        state.buffer.append(
            InvestigationBufferRow(
                doc_id="d1",
                filename="test.csv",
                notes_summary="Found issue",
                fraud_likelihood=0.6,
                primary_next_doc="next.csv",
                open_questions=["Why no receipt?"],
            )
        )
        output = state.format_buffer_for_llm()
        assert "test.csv" in output
        assert "Found issue" in output
        assert "0.60" in output
        assert "next.csv" in output
        assert "Why no receipt?" in output

    def test_terminated_by_max_iterations(self) -> None:
        state = InvestigationState(max_iterations=3)
        state.stack = ["a"]
        state.iteration_count = 3
        assert state.is_terminated()

    def test_terminated_by_empty_stack(self) -> None:
        state = InvestigationState()
        state.stack = []
        state.iteration_count = 1  # at least one step done
        assert state.is_terminated()

    def test_not_terminated_with_work_remaining(self) -> None:
        state = InvestigationState(max_iterations=10)
        state.stack = ["a", "b"]
        state.iteration_count = 2
        assert not state.is_terminated()
